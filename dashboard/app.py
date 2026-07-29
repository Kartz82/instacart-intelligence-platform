import dash
from dash import dcc, html, dash_table, Input, Output
from dash.dash_table.Format import Format, Group, Scheme, Symbol
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import psycopg2
from sqlalchemy import create_engine
from pathlib import Path
import os
import sys

EXPORT_MODE = "--export" in sys.argv
BRAVE_BROWSER_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
if EXPORT_MODE and "BROWSER_PATH" not in os.environ and Path(BRAVE_BROWSER_PATH).exists():
    os.environ["BROWSER_PATH"] = BRAVE_BROWSER_PATH


# ── CONNECTION ────────────────────────────────────────────────
ENGINE = create_engine(
    "postgresql://postgres:postgres@localhost:5434/instacart_db"
)

def q(sql):
    """Run a query against the warehouse.

    There is deliberately no CSV fallback. Every query here reads a dbt mart, and the
    marts are the only definition of these metrics - a local fallback would have to
    reimplement that logic and would silently drift from it. If the warehouse is not
    reachable, failing loudly is correct: the alternative is a dashboard that renders
    numbers which no longer match the models.
    """
    return pd.read_sql(sql, ENGINE)

# ── LOAD DATA ─────────────────────────────────────────────────
# Every query below reads a dbt mart, never the raw tables or the 33.8M-row fact.
# The marts are already aggregated to a BI-sized grain (mart_time_patterns is 168 rows,
# mart_reorder_behavior 134, mart_executive_kpis 1), so the dashboard does no aggregation
# of its own and the page loads without scanning the fact table. This is the same
# separation the Power BI plan uses, and it is the reason the BI layer stays fast at
# scale - see docs/decisions.md, decision 6.

rfm = q("""
    SELECT behavioral_segment            AS customer_segment,
           COUNT(*)                      AS customer_count,
           ROUND(AVG(total_orders),1)    AS avg_orders,
           ROUND(AVG(total_items_purchased),1) AS avg_items
    FROM analytics_kpis.mart_customer_segments
    GROUP BY behavioral_segment
    ORDER BY customer_count DESC
""")

dept = q("""
    SELECT department_name       AS department,
           SUM(total_order_items) AS total_purchases,
           ROUND(
               SUM(total_order_items * reorder_rate)
               / NULLIF(SUM(total_order_items), 0),
               3
           )                      AS reorder_rate
    FROM analytics_kpis.mart_reorder_behavior
    GROUP BY department_name
    ORDER BY total_purchases DESC
    LIMIT 15
""")

top_products = q("""
    SELECT product_name,
           total_order_items AS purchase_count,
           ROUND(reorder_rate, 3) AS reorder_rate
    FROM analytics_kpis.mart_product_performance
    ORDER BY total_order_items DESC
    LIMIT 20
""")

orders_by_dow = q("""
    SELECT order_dow         AS day_of_week,
           order_day_of_week AS day_name,
           SUM(total_orders) AS order_count
    FROM analytics_analysis.mart_time_patterns
    GROUP BY order_dow, order_day_of_week
    ORDER BY day_of_week
""")

basket = q("""
    SELECT product_a_name AS antecedents,
           product_b_name AS consequents,
           support,
           confidence_a_to_b AS confidence,
           lift
    FROM analytics_analysis.mart_basket_affinity
    ORDER BY lift DESC
    LIMIT 15
""")

# The 168-row day-of-week x hour grid, read whole. dim_time is generated rather than
# derived, so every slot exists even at zero volume and the heatmap keeps its shape.
time_patterns = q("""
    SELECT order_dow,
           order_day_of_week,
           order_hour_of_day,
           daypart,
           is_weekend,
           total_orders,
           average_basket_size,
           reorder_rate
    FROM analytics_analysis.mart_time_patterns
    ORDER BY order_dow, order_hour_of_day
""")

cohort = q("""
    SELECT observed_order_number,
           starting_customers,
           active_customers,
           retention_rate
    FROM analytics_analysis.mart_cohort_retention
    ORDER BY observed_order_number
""")

reorder_behavior = q("""
    SELECT department_name,
           aisle_name,
           total_order_items,
           reorder_rate,
           reorder_rate_vs_platform,
           distinct_customers
    FROM analytics_kpis.mart_reorder_behavior
    ORDER BY total_order_items DESC
""")

_kpis = q("""
    SELECT total_orders,
           total_customers,
           total_products,
           reorder_rate
    FROM analytics_kpis.mart_executive_kpis
""")
total_orders    = int(_kpis['total_orders'][0])
total_customers = int(_kpis['total_customers'][0])
total_products  = int(_kpis['total_products'][0])
reorder_rate    = round(float(_kpis['reorder_rate'][0]) * 100, 1)

# ── DESIGN SYSTEM ─────────────────────────────────────────────
# One palette, applied by the job each colour does, rather than a different scale
# per chart. Validated with the data-viz palette checker rather than chosen by eye.
#
#   sequential (magnitude)  - one blue hue, light -> dark. Heatmap, treemap.
#   ordinal    (ranked tiers) - four steps of that same blue, low -> high engagement.
#                               Customer segments are a ladder, not unrelated
#                               categories, so a ranked ramp is the honest encoding.
#   diverging  (polarity)   - blue <-> red with a grey midpoint, for "above or below
#                             the platform average", where zero is the meaningful centre.
#   status                  - reserved for state, never reused as a series colour.

INK          = '#0b0b0b'   # primary text
INK_MUTED    = '#52514e'   # secondary text
SURFACE      = '#ffffff'
SURFACE_ALT  = '#fcfcfb'
GRID         = '#e7e6e3'

BLUE         = '#2a78d6'   # categorical slot 1 / brand
ORANGE       = '#eb6834'   # categorical slot 2
DARK         = '#1a1a19'
MUTED        = INK_MUTED
LIGHT        = SURFACE_ALT

# Sequential blue ramp, steps 100 -> 700.
SEQ_BLUE = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']

# Diverging: blue (above average) <-> grey midpoint <-> red (below average).
DIVERGING = [[0.0, '#d03b3b'], [0.5, '#f0efec'], [1.0, '#2a78d6']]

# Ordinal engagement ladder. Validated light->dark, monotone lightness, single hue,
# light end clears the surface at 2.06:1.
SEG_COLORS = {
    'At Risk':             '#86b6ef',
    'Moderate Engagement': '#3987e5',
    'Loyal Routine':       '#256abf',
    'High Engagement':     '#104281',
}
SEGMENT_ORDER = ['At Risk', 'Moderate Engagement', 'Loyal Routine', 'High Engagement']

STATUS_GOOD     = '#0ca30c'
STATUS_CRITICAL = '#d03b3b'


# ── CHARTS ────────────────────────────────────────────────────
def chart_layout(fig, h=460, legend=True):
    """House style: recessive axes, generous type, no chart junk."""
    fig.update_layout(
        plot_bgcolor=SURFACE_ALT, paper_bgcolor=SURFACE,
        font=dict(family='Inter, -apple-system, Segoe UI, Arial', color=INK, size=13),
        title=dict(font=dict(size=17, color=INK), x=0, xanchor='left', pad=dict(b=14)),
        margin=dict(l=70, r=40, t=70, b=60),
        height=h,
        autosize=True,
        showlegend=legend,
        legend=dict(bgcolor='rgba(0,0,0,0)', orientation='h',
                    yanchor='bottom', y=1.01, xanchor='right', x=1),
        hoverlabel=dict(font_size=13, font_family='Inter, Arial'),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID,
                     title_font=dict(size=13, color=INK_MUTED),
                     tickfont=dict(color=INK_MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID,
                     title_font=dict(size=13, color=INK_MUTED),
                     tickfont=dict(color=INK_MUTED))
    return fig


# Customer segments - ranked tiers, so a single-hue ordinal ramp read low -> high.
# One series, directly labelled, so no legend box is needed.
_seg = rfm.copy()
_seg['customer_segment'] = pd.Categorical(_seg['customer_segment'], SEGMENT_ORDER, ordered=True)
_seg = _seg.sort_values('customer_segment')
_seg['share'] = _seg['customer_count'] / _seg['customer_count'].sum()
_seg['label'] = _seg.apply(
    lambda r: f"{r['customer_count']:,}  ·  {r['share']:.1%}", axis=1)

fig_rfm = px.bar(
    _seg, x='customer_count', y='customer_segment', orientation='h',
    color='customer_segment', color_discrete_map=SEG_COLORS, text='label',
    title='Customer base by engagement tier',
)
fig_rfm.update_traces(textposition='outside', textfont=dict(size=13, color=INK),
                      marker_line_width=0,
                      hovertemplate='<b>%{y}</b><br>%{x:,} customers<extra></extra>')
fig_rfm.update_xaxes(title='Customers', tickformat=',',
                     range=[0, _seg['customer_count'].max() * 1.42])
fig_rfm.update_yaxes(title='')
fig_rfm = chart_layout(fig_rfm, h=420, legend=False)

# Retention curve. A line is the right form for a monotone decline over an ordered
# sequence; the fill underneath carries the "how much is left" reading.
fig_cohort = px.line(
    cohort, x='observed_order_number', y='retention_rate', markers=True,
    title='Customer retention by observed order number',
)
fig_cohort.update_traces(
    line=dict(color=BLUE, width=2.5), marker=dict(size=8, color=BLUE),
    fill='tozeroy', fillcolor='rgba(42,120,214,0.10)',
    hovertemplate='Order %{x}<br><b>%{y:.1%}</b> still active<extra></extra>')
fig_cohort.update_yaxes(title='Customers still ordering', tickformat='.0%', range=[0, 1.04])
fig_cohort.update_xaxes(title='Observed order number', dtick=2)
fig_cohort = chart_layout(fig_cohort, h=420, legend=False)

# Reorder rate gauge. A single headline number gets a single-value form, not a chart.
fig_gauge = go.Figure(go.Indicator(
    mode='gauge+number',
    value=reorder_rate,
    number={'suffix': '%', 'font': {'size': 46, 'color': INK}},
    gauge={
        'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': GRID,
                 'tickfont': {'size': 12, 'color': INK_MUTED}},
        'bar': {'color': BLUE, 'thickness': 0.7},
        'bgcolor': SURFACE_ALT,
        'borderwidth': 0,
        'steps': [{'range': [0, 100], 'color': SURFACE_ALT}],
    },
    title={'text': 'Platform reorder rate', 'font': {'size': 15, 'color': INK_MUTED}},
))
fig_gauge = chart_layout(fig_gauge, h=420, legend=False)
fig_gauge.update_layout(margin=dict(l=45, r=45, t=70, b=30))

# Demand heatmap. Two cyclical axes at once - the only form that shows both, and the
# reason mart_time_patterns keeps a generated 168-slot grid.
_grid = time_patterns.pivot_table(
    index='order_day_of_week', columns='order_hour_of_day',
    values='total_orders', aggfunc='sum',
).reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])

fig_heatmap = px.imshow(
    _grid, color_continuous_scale=SEQ_BLUE, aspect='auto',
    labels=dict(x='Hour of day', y='', color='Orders'),
    title='When customers order — day of week by hour',
)
fig_heatmap.update_traces(
    hovertemplate='<b>%{y} %{x}:00</b><br>%{z:,} orders<extra></extra>')
fig_heatmap.update_xaxes(dtick=2, title='Hour of day')
fig_heatmap.update_coloraxes(colorbar=dict(title='Orders', tickformat=',', thickness=14))
fig_heatmap = chart_layout(fig_heatmap, h=460, legend=False)

# Weekly volume. One series, directly labelled.
fig_dow = px.bar(
    orders_by_dow, x='day_name', y='order_count', text='order_count',
    title='Order volume by day of week',
)
fig_dow.update_traces(marker_color=BLUE, marker_line_width=0,
                      textposition='outside', textfont=dict(size=12, color=INK),
                      texttemplate='%{text:,}',
                      hovertemplate='<b>%{x}</b><br>%{y:,} orders<extra></extra>')
fig_dow.update_yaxes(title='Orders', tickformat=',',
                     range=[0, orders_by_dow['order_count'].max() * 1.18])
fig_dow.update_xaxes(title='')
fig_dow = chart_layout(fig_dow, h=420, legend=False)

# Weekday vs weekend by daypart. Two genuine categories, so this is the one categorical
# encoding in the dashboard: slots 1 and 2, validated at CVD dE 24.7 with a legend.
# It answers a question no other chart here does - whether the weekly peak is a
# weekday-commute pattern or a weekend-stock-up one.
_dayparts = ['Overnight', 'Morning', 'Midday', 'Afternoon', 'Evening']
_daypart = (
    time_patterns
    .assign(period=lambda d: d['is_weekend'].map({True: 'Weekend', False: 'Weekday'}))
    .groupby(['daypart', 'period'], as_index=False)['total_orders'].sum()
)
_daypart['daypart'] = pd.Categorical(_daypart['daypart'], _dayparts, ordered=True)
_daypart = _daypart.sort_values(['daypart', 'period'])

fig_daypart = px.bar(
    _daypart, x='daypart', y='total_orders', color='period', barmode='group',
    color_discrete_map={'Weekday': BLUE, 'Weekend': ORANGE},
    title='Weekday vs weekend demand, by time of day',
)
fig_daypart.update_traces(marker_line_width=0,
                          hovertemplate='<b>%{x} · %{fullData.name}</b><br>%{y:,} orders<extra></extra>')
fig_daypart.update_yaxes(title='Orders', tickformat=',')
fig_daypart.update_xaxes(title='')
fig_daypart.update_layout(legend_title_text='')
fig_daypart = chart_layout(fig_daypart, h=440)

# Category treemap. Hierarchy plus magnitude in one form; area carries volume and the
# sequential ramp carries reorder rate.
fig_treemap = px.treemap(
    reorder_behavior, path=['department_name', 'aisle_name'],
    values='total_order_items', color='reorder_rate',
    color_continuous_scale=SEQ_BLUE,
    title='Category mix — department and aisle, shaded by reorder rate',
)
fig_treemap.update_traces(
    marker_line_width=2, marker_line_color=SURFACE,
    root_color=SURFACE, tiling=dict(pad=3),
    textfont=dict(size=13, family='Inter, Arial'),
    hovertemplate='<b>%{label}</b><br>%{value:,} items<br>Reorder rate %{color:.1%}<extra></extra>')
fig_treemap.update_coloraxes(colorbar=dict(title='Reorder<br>rate', tickformat='.0%',
                                           thickness=14))
fig_treemap = chart_layout(fig_treemap, h=560, legend=False)
fig_treemap.update_layout(margin=dict(l=10, r=10, t=70, b=10))

# Aisle loyalty vs the platform average. Zero is the meaningful centre, so this is a
# diverging encoding - the one chart that answers "which categories beat the norm".
_loyalty = reorder_behavior.nlargest(12, 'total_order_items').copy()
_loyalty = _loyalty.sort_values('reorder_rate_vs_platform')
_loyalty['aisle_label'] = _loyalty['aisle_name'].str.title()
_bound = _loyalty['reorder_rate_vs_platform'].abs().max()

fig_loyalty = px.bar(
    _loyalty, x='reorder_rate_vs_platform', y='aisle_label', orientation='h',
    color='reorder_rate_vs_platform', color_continuous_scale=DIVERGING,
    range_color=[-_bound, _bound],
    title='Aisle loyalty vs platform average — highest-volume aisles',
)
fig_loyalty.update_traces(
    marker_line_width=0,
    hovertemplate='<b>%{y}</b><br>%{x:+.1%} vs platform average<extra></extra>')
fig_loyalty.update_xaxes(title='Reorder rate vs platform average', tickformat='+.0%')
fig_loyalty.update_yaxes(title='')
fig_loyalty.update_coloraxes(showscale=False)
fig_loyalty.add_vline(x=0, line_width=1.5, line_color=INK_MUTED)
fig_loyalty = chart_layout(fig_loyalty, h=520, legend=False)

# Top products.
_prod = top_products.sort_values('purchase_count').copy()
fig_prod = px.bar(
    _prod, x='purchase_count', y='product_name', orientation='h',
    color='reorder_rate', color_continuous_scale=SEQ_BLUE,
    title='Top 20 products by order volume, shaded by reorder rate',
)
fig_prod.update_traces(
    marker_line_width=0,
    hovertemplate='<b>%{y}</b><br>%{x:,} items<br>Reorder rate %{marker.color:.1%}<extra></extra>')
fig_prod.update_xaxes(title='Order line items', tickformat=',')
fig_prod.update_yaxes(title='')
fig_prod.update_coloraxes(colorbar=dict(title='Reorder<br>rate', tickformat='.0%',
                                        thickness=14))
fig_prod = chart_layout(fig_prod, h=640, legend=False)

# Basket affinity. A scatter is the right form for two continuous measures; size adds
# lift as a third. Kept to one series so the all-pairs colour cap does not apply.
fig_basket = px.scatter(
    basket, x='support', y='confidence', size='lift', color='lift',
    color_continuous_scale=SEQ_BLUE, size_max=42,
    hover_data=['antecedents', 'consequents'],
    title='Product pair affinity — how often, and how predictive',
)
fig_basket.update_traces(
    marker=dict(line=dict(width=2, color=SURFACE)),
    hovertemplate=('<b>%{customdata[0]}</b><br>with %{customdata[1]}<br>'
                   'Support %{x:.4%}<br>Confidence %{y:.1%}<br>'
                   'Lift %{marker.size:,.0f}x<extra></extra>'))
fig_basket.update_xaxes(title='Support — share of all orders containing both',
                        tickformat='.3%')
fig_basket.update_yaxes(title='Confidence — chance the second is bought too',
                        tickformat='.0%')
fig_basket.update_coloraxes(colorbar=dict(title='Lift', thickness=14))
fig_basket = chart_layout(fig_basket, h=520, legend=False)

def kpi(label, value, color=BLUE):
    return dbc.Col(dbc.Card([
        dbc.CardBody([
            html.P(label, className='text-muted mb-1',
                   style={'fontSize':'0.72rem','letterSpacing':'0.1em',
                          'textTransform':'uppercase','fontWeight':'600'}),
            html.H3(str(value),
                    style={'color':color,'fontFamily':'monospace',
                           'fontWeight':'700','marginBottom':'0'}),
        ])
    ], style={'borderRadius':'12px','border':f'1px solid {GRID}',
              'boxShadow':'0 2px 8px rgba(0,0,0,0.06)'}),
    xs=12, sm=6, md=3)

# ── APP LAYOUT ────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title='Instacart Intelligence Platform'
)

NAV = dbc.Navbar(
    dbc.Container([
        html.Span("🛒 Instacart Intelligence Platform",
                  style={'color':'white','fontWeight':'700',
                         'fontSize':'1.1rem','letterSpacing':'-0.01em'}),
        html.Span("Customer · Product · Basket · Operations Analytics",
                  style={'color':'rgba(255,255,255,0.6)',
                         'fontSize':'0.78rem','marginLeft':'16px'}),
    ], fluid=True),
    color=DARK, dark=True,
    style={'borderBottom':f'3px solid {BLUE}','padding':'14px 0'}
)

# ── LAYOUT HELPERS ────────────────────────────────────────────
def card(figure):
    """One chart in a card, full width. Charts get a tab to themselves rather than
    sharing a row: stacking three plots per page shrinks each one until axis labels and
    category names stop being legible, which defeats the point of the chart."""
    return dbc.Card(dbc.CardBody(
        dcc.Graph(
            figure=figure,
            config={'displayModeBar': False, 'responsive': True},
            style={'width': '100%'},
        )
    ), style={'borderRadius': '12px', 'border': f'1px solid {GRID}'})


def full(figure):
    return dbc.Row([dbc.Col(card(figure), md=12)], className='g-3')


def tab(label, tab_id, *children):
    return dbc.Tab(
        label=label, tab_id=tab_id,
        children=[html.Br(), *children],
        tab_style={'padding': '10px 22px'},
        label_style={'fontWeight': '600', 'fontSize': '0.9rem', 'color': INK_MUTED},
        active_label_style={'color': INK},
    )


SEGMENT_TABLE = dbc.Card(dbc.CardBody([
    html.H6("Segment Breakdown", style={'fontWeight': '600', 'marginBottom': '16px'}),
    dash_table.DataTable(
        data=_seg.to_dict('records'),
        columns=[
            {'name': 'Segment',    'id': 'customer_segment'},
            {'name': 'Customers',  'id': 'customer_count',
             'type': 'numeric', 'format': Format(group=Group.yes)},
            {'name': 'Share',      'id': 'share',
             'type': 'numeric', 'format': Format(precision=1, scheme=Scheme.percentage)},
            {'name': 'Avg Orders', 'id': 'avg_orders'},
            {'name': 'Avg Items',  'id': 'avg_items'},
        ],
        sort_action='native',
        style_table={'overflowX': 'auto'},
        style_cell={'fontFamily': 'Inter, Arial', 'fontSize': '13px',
                    'padding': '10px 14px', 'border': f'1px solid {GRID}'},
        style_header={'backgroundColor': INK, 'color': 'white',
                      'fontWeight': '600', 'fontSize': '12px'},
        style_data_conditional=[
            {'if': {'filter_query': '{customer_segment} = "High Engagement"'},
             'backgroundColor': '#e8f1fd', 'color': '#104281', 'fontWeight': '600'},
            {'if': {'filter_query': '{customer_segment} = "At Risk"'},
             'backgroundColor': '#fbeaea', 'color': STATUS_CRITICAL, 'fontWeight': '600'},
        ],
    )
]), style={'borderRadius': '12px', 'border': f'1px solid {GRID}'})

RULES_TABLE = dbc.Card(dbc.CardBody([
    html.H6("Top Association Rules by Lift",
            style={'fontWeight': '600', 'marginBottom': '16px'}),
    dash_table.DataTable(
        data=basket[['antecedents', 'consequents',
                     'support', 'confidence', 'lift']].to_dict('records'),
        columns=[
            {'name': 'If customer buys...', 'id': 'antecedents'},
            {'name': 'They also buy...',    'id': 'consequents'},
            {'name': 'Share of orders',     'id': 'support', 'type': 'numeric',
             'format': Format(precision=3, scheme=Scheme.percentage)},
            {'name': 'Chance of second',    'id': 'confidence', 'type': 'numeric',
             'format': Format(precision=1, scheme=Scheme.percentage)},
            {'name': 'Lift vs baseline',    'id': 'lift', 'type': 'numeric',
             'format': Format(precision=0, scheme=Scheme.fixed, group=Group.yes).symbol(
                 Symbol.yes).symbol_suffix('x')},
        ],
        style_table={'overflowX': 'auto'},
        style_cell={'fontFamily': 'Inter, Arial', 'fontSize': '13px',
                    'padding': '10px 14px', 'border': f'1px solid {GRID}',
                    'textAlign': 'left'},
        style_cell_conditional=[
            {'if': {'column_id': 'antecedents'}, 'minWidth': '240px'},
            {'if': {'column_id': 'consequents'}, 'minWidth': '240px'},
        ],
        style_header={'backgroundColor': INK, 'color': 'white',
                      'fontWeight': '600', 'fontSize': '12px'},
        sort_action='native',
        filter_action='native',
    )
]), style={'borderRadius': '12px', 'border': f'1px solid {GRID}'})


TABS = dbc.Tabs([

    # Six pages, matching the five-page Power BI specification plus a dedicated
    # product page. Each carries at most two visual blocks: a chart squeezed into a
    # third of a crowded page stops being readable, which defeats the point of it.

    tab('Executive Overview', 'overview',
        dbc.Row([
            kpi('Total Orders',     f"{int(total_orders):,}"),
            kpi('Unique Customers', f"{int(total_customers):,}"),
            kpi('Products',         f"{int(total_products):,}"),
            kpi('Reorder Rate',     f"{reorder_rate}%", ORANGE),
        ], className='g-3 mb-4'),
        dbc.Row([
            dbc.Col(card(fig_gauge), md=4),
            dbc.Col(card(fig_cohort), md=8),
        ], className='g-3'),
        ),

    tab('Customer Segments', 'segments',
        dbc.Row([
            dbc.Col(card(fig_rfm), md=7),
            dbc.Col(SEGMENT_TABLE, md=5),
        ], className='g-3'),
        ),

    tab('Demand Patterns', 'demand',
        full(fig_heatmap),
        html.Br(),
        dbc.Row([
            dbc.Col(card(fig_dow), md=6),
            dbc.Col(card(fig_daypart), md=6),
        ], className='g-3'),
        ),

    tab('Category Performance', 'categories',
        full(fig_treemap),
        html.Br(),
        full(fig_loyalty),
        ),

    tab('Product Performance', 'products', full(fig_prod)),

    tab('Basket & Cross-sell', 'basket',
        full(fig_basket),
        html.Br(),
        dbc.Row([dbc.Col(RULES_TABLE, md=12)], className='g-3'),
        ),

], id='main-tabs', active_tab='overview', style={'marginTop':'8px'})

app.clientside_callback(
    """
    function(active_tab) {
        // Defer past the tab's own render, then let Plotly re-measure.
        setTimeout(function() { window.dispatchEvent(new Event('resize')); }, 60);
        return window.dash_clientside.no_update;
    }
    """,
    Output('tab-resize-sink', 'children'),
    Input('main-tabs', 'active_tab'),
)

app.layout = dbc.Container([
    NAV,
    html.Br(),
    TABS,
    # Write-only target for the tab-resize callback; Dash requires an Output.
    html.Div(id='tab-resize-sink', style={'display': 'none'}),
    html.Br(),
    html.Hr(style={'borderColor':GRID}),
    html.P(
        "Instacart Intelligence Platform · 3.4M Orders · 206K Customers · "
        "49K Products · Built with Python, PostgreSQL, Plotly Dash",
        className='text-center text-muted',
        style={'fontSize':'0.72rem','letterSpacing':'0.08em'}
    ),
    ], fluid=True, style={'backgroundColor':LIGHT,'minHeight':'100vh','padding':'0'})

PORTFOLIO_BACKGROUND = "#050A14"
PORTFOLIO_PANEL = "#0B1220"
PORTFOLIO_CARD = "#111827"
PORTFOLIO_BORDER = "#243244"
PORTFOLIO_GRID = "rgba(148, 163, 184, 0.16)"
PORTFOLIO_TEXT = "#E5E7EB"
PORTFOLIO_MUTED = "#94A3B8"

PORTFOLIO_BLUE = "#38BDF8"
PORTFOLIO_TEAL = "#14B8A6"
PORTFOLIO_GREEN = "#10B981"
PORTFOLIO_AMBER = "#F59E0B"
PORTFOLIO_ORANGE = "#F97316"
PORTFOLIO_ROSE = "#FB7185"
PORTFOLIO_RED = "#F43F5E"
PORTFOLIO_PURPLE = "#A855F7"
PORTFOLIO_GRAY = "#64748B"

# Sequential ramp for the dark portfolio surface: one hue, dark -> light. Replaces the
# blue/teal/amber/rose scales previously used here - a multi-hue rainbow encoding a
# single magnitude has no perceptual order, so readers cannot rank two colours without
# consulting the legend.
PORTFOLIO_SEQ = ["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"]

PORTFOLIO_WIDTH = 1600
PORTFOLIO_HEIGHT = 900

def _clean_rule_item(value):
    return (
        str(value)
        .replace("frozenset({", "")
        .replace("})", "")
        .replace("'", "")
        .replace('"', "")
        .strip()
    )

def _portfolio_base_layout(fig, title, subtitle):
    fig.update_layout(
        width=PORTFOLIO_WIDTH,
        height=PORTFOLIO_HEIGHT,
        plot_bgcolor=PORTFOLIO_PANEL,
        paper_bgcolor=PORTFOLIO_BACKGROUND,
        font=dict(family="Inter, Arial, sans-serif", color=PORTFOLIO_TEXT, size=21),
        margin=dict(l=150, r=90, t=185, b=100),
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:23px;color:{PORTFOLIO_MUTED}'>{subtitle}</span>",
            x=0.06,
            y=0.95,
            xanchor="left",
            yanchor="top",
            font=dict(size=46, color=PORTFOLIO_TEXT),
        ),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=PORTFOLIO_MUTED, size=18)),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=PORTFOLIO_GRID,
        zeroline=False,
        linecolor=PORTFOLIO_BORDER,
        tickfont=dict(color=PORTFOLIO_MUTED, size=18),
        title_font=dict(color=PORTFOLIO_TEXT, size=21),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=PORTFOLIO_GRID,
        zeroline=False,
        linecolor=PORTFOLIO_BORDER,
        tickfont=dict(color=PORTFOLIO_MUTED, size=18),
        title_font=dict(color=PORTFOLIO_TEXT, size=21),
    )
    return fig

def _export_basket_affinity_map(output_path):
    rules = pd.read_csv("data/processed/market_basket_rules.csv")
    rules["antecedents"] = rules["antecedents"].map(_clean_rule_item)
    rules["consequents"] = rules["consequents"].map(_clean_rule_item)
    rules["rule"] = rules["antecedents"] + " -> " + rules["consequents"]
    rules = rules.sort_values(["lift", "confidence", "support"], ascending=False).head(45).copy()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rules["support"],
        y=rules["confidence"],
        mode="markers",
        marker=dict(
            size=rules["lift"] * 14,
            sizemode="diameter",
            color=rules["lift"],
            colorscale=PORTFOLIO_SEQ,
            showscale=True,
            colorbar=dict(
                title=dict(text="Lift", font=dict(color=PORTFOLIO_TEXT, size=18)),
                tickfont=dict(color=PORTFOLIO_MUTED, size=16),
                outlinecolor=PORTFOLIO_BORDER,
            ),
            line=dict(color="rgba(229, 231, 235, 0.55)", width=1),
            opacity=0.88,
        ),
        text=rules["rule"],
        customdata=rules[["lift"]],
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Support %{x:.2%}<br>"
            "Confidence %{y:.2%}<br>"
            "Lift %{customdata[0]:.2f}x<extra></extra>"
        ),
        showlegend=False,
    ))

    highlight_mask = (
        rules["antecedents"].str.contains("Banana", case=False, regex=False)
        & rules["consequents"].str.contains("Organic Strawberries", case=False, regex=False)
    )
    if highlight_mask.any():
        highlight = rules[highlight_mask].iloc[0]
    else:
        highlight = rules.iloc[0]

    fig.add_trace(go.Scatter(
        x=[highlight["support"]],
        y=[highlight["confidence"]],
        mode="markers",
        marker=dict(
            size=max(float(highlight["lift"]) * 19, 42),
            color=PORTFOLIO_ORANGE,
            line=dict(color=PORTFOLIO_TEXT, width=3),
            opacity=1,
        ),
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.add_annotation(
        x=highlight["support"],
        y=highlight["confidence"],
        text=(
            f"<b>{highlight['antecedents']} -> {highlight['consequents']}</b><br>"
            f"{highlight['lift']:.2f}x lift"
        ),
        showarrow=True,
        arrowcolor=PORTFOLIO_ORANGE,
        arrowwidth=2,
        ax=150,
        ay=-95,
        bgcolor=PORTFOLIO_CARD,
        bordercolor=PORTFOLIO_ORANGE,
        borderwidth=1,
        font=dict(color=PORTFOLIO_TEXT, size=20),
        align="left",
    )

    for _, row in rules.sort_values("lift", ascending=False).head(3).iterrows():
        if row.name == highlight.name:
            continue
        fig.add_annotation(
            x=row["support"],
            y=row["confidence"],
            text=f"{row['antecedents']} -><br>{row['consequents']}<br><b>{row['lift']:.2f}x</b>",
            showarrow=True,
            arrowcolor=PORTFOLIO_BORDER,
            arrowwidth=1,
            ax=-95,
            ay=60,
            bgcolor="rgba(17, 24, 39, 0.88)",
            bordercolor=PORTFOLIO_BORDER,
            borderwidth=1,
            font=dict(color=PORTFOLIO_TEXT, size=16),
            align="left",
        )

    fig = _portfolio_base_layout(
        fig,
        "Basket Affinity Map",
        "Top product-pair relationships by support, confidence, and lift",
    )
    fig.update_xaxes(title="Support", tickformat=".1%", range=[0, max(rules["support"].max() * 1.28, 0.025)])
    fig.update_yaxes(title="Confidence", tickformat=".0%", range=[0, max(rules["confidence"].max() * 1.22, 0.42)])
    fig.write_image(output_path, width=PORTFOLIO_WIDTH, height=PORTFOLIO_HEIGHT, scale=2)

def _export_category_performance(output_path):
    source = dept.sort_values("total_purchases", ascending=True).copy()
    source["reorder_pct"] = source["reorder_rate"] * 100

    fig = go.Figure(go.Bar(
        x=source["total_purchases"],
        y=source["department"],
        orientation="h",
        marker=dict(
            color=source["reorder_rate"],
            colorscale=PORTFOLIO_SEQ,
            line=dict(color="rgba(229, 231, 235, 0.28)", width=1),
            colorbar=dict(
                title=dict(text="Reorder rate", font=dict(color=PORTFOLIO_TEXT, size=18)),
                tickformat=".0%",
                tickfont=dict(color=PORTFOLIO_MUTED, size=16),
                outlinecolor=PORTFOLIO_BORDER,
            ),
        ),
        text=source["total_purchases"].map(lambda value: f"{int(value):,}"),
        textposition="outside",
        textfont=dict(color=PORTFOLIO_TEXT, size=17),
        customdata=source[["reorder_pct"]],
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Purchases %{x:,}<br>"
            "Reorder rate %{customdata[0]:.1f}%<extra></extra>"
        ),
    ))

    fig = _portfolio_base_layout(
        fig,
        "Category Performance",
        "Purchase volume and reorder behavior across departments and products",
    )
    fig.update_layout(margin=dict(l=220, r=160, t=185, b=95))
    fig.update_xaxes(title="Total purchases", tickformat=",", range=[0, source["total_purchases"].max() * 1.18])
    fig.update_yaxes(title="", tickfont=dict(color=PORTFOLIO_TEXT, size=19))
    fig.write_image(output_path, width=PORTFOLIO_WIDTH, height=PORTFOLIO_HEIGHT, scale=2)

def _export_customer_segments(output_path):
    # Ordered least- to most-engaged, so the exported bar chart reads bottom-to-top as an
    # engagement ladder. Names match mart_customer_segments.behavioral_segment exactly.
    segment_order = [
        "At Risk",
        "Moderate Engagement",
        "Loyal Routine",
        "High Engagement",
    ]
    # Same ordinal ladder as the app, stepped for the dark surface: engagement is
    # ranked, so the ramp is one hue read low -> high rather than four unrelated colours.
    segment_colors = {
        "At Risk": "#184f95",
        "Moderate Engagement": "#256abf",
        "Loyal Routine": "#3987e5",
        "High Engagement": "#9ec5f4",
    }
    source = rfm[["customer_segment", "customer_count"]].copy()
    source["customer_count"] = source["customer_count"].astype(int)
    source["customer_segment"] = pd.Categorical(source["customer_segment"], segment_order, ordered=True)
    source = source.sort_values("customer_segment")
    total = source["customer_count"].sum()
    source["share"] = source["customer_count"] / total
    colors = source["customer_segment"].astype(str).map(segment_colors)

    fig = go.Figure(go.Bar(
        x=source["customer_count"],
        y=source["customer_segment"].astype(str),
        orientation="h",
        marker=dict(color=colors, line=dict(color="rgba(229, 231, 235, 0.32)", width=1)),
        text=source.apply(lambda row: f"{int(row['customer_count']):,}  |  {row['share']:.1%}", axis=1),
        textposition="outside",
        textfont=dict(color=PORTFOLIO_TEXT, size=21),
        hovertemplate="<b>%{y}</b><br>%{x:,} customers<extra></extra>",
    ))

    fig = _portfolio_base_layout(
        fig,
        "Customer Segment Breakdown",
        "Customer mix by behavioral segment and reorder activity",
    )
    fig.update_layout(margin=dict(l=260, r=180, t=185, b=95))
    fig.update_xaxes(title="Customers", tickformat=",", range=[0, source["customer_count"].max() * 1.24])
    fig.update_yaxes(title="", tickfont=dict(color=PORTFOLIO_TEXT, size=22))

    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.985,
        y=1.08,
        text=f"<b>{total:,}</b><br><span style='color:{PORTFOLIO_MUTED}'>customers represented</span>",
        showarrow=False,
        align="right",
        font=dict(color=PORTFOLIO_TEXT, size=24),
        bgcolor="rgba(17, 24, 39, 0.72)",
        bordercolor=PORTFOLIO_BORDER,
        borderwidth=1,
    )
    fig.write_image(output_path, width=PORTFOLIO_WIDTH, height=PORTFOLIO_HEIGHT, scale=2)

def save_portfolio_figures():
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    targets = {
        "basket": reports_dir / "basket_affinity_map.png",
        "category": reports_dir / "category_performance.png",
        "segments": reports_dir / "customer_segments.png",
    }

    _export_basket_affinity_map(targets["basket"])
    _export_category_performance(targets["category"])
    _export_customer_segments(targets["segments"])
    return targets

if __name__ == '__main__':
    if EXPORT_MODE:
        saved = save_portfolio_figures()
        for path in saved.values():
            print(path)
    else:
        # debug defaults off: the Dash debug toolbar overlays the bottom-right corner and
        # ends up in dashboard screenshots. Set DASH_DEBUG=1 for local development.
        app.run(debug=os.environ.get("DASH_DEBUG") == "1", port=8050)
