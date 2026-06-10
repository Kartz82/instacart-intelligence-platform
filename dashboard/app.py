import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import psycopg2
from sqlalchemy import create_engine

# ── CONNECTION ────────────────────────────────────────────────
ENGINE = create_engine(
    "postgresql://postgres:postgres@localhost:5434/instacart_db"
)

def q(sql):
    return pd.read_sql(sql, ENGINE)

# ── LOAD DATA ─────────────────────────────────────────────────
rfm = q("""
    SELECT customer_segment,
           COUNT(*)                    AS customer_count,
           ROUND(AVG(total_orders),1)  AS avg_orders,
           ROUND(AVG(total_items_purchased),1) AS avg_items
    FROM customer_rfm_segments
    GROUP BY customer_segment
    ORDER BY customer_count DESC
""")

dept = q("""
    SELECT d.department,
           COUNT(op.order_id)          AS total_purchases,
           ROUND(AVG(op.reordered),3)  AS reorder_rate
    FROM order_products op
    JOIN products p  ON op.product_id  = p.product_id
    JOIN departments d ON p.department_id = d.department_id
    GROUP BY d.department
    ORDER BY total_purchases DESC
    LIMIT 15
""")

top_products = q("""
    SELECT p.product_name,
           COUNT(op.order_id)         AS purchase_count,
           ROUND(AVG(op.reordered),3) AS reorder_rate
    FROM order_products op
    JOIN products p ON op.product_id = p.product_id
    GROUP BY p.product_name
    ORDER BY purchase_count DESC
    LIMIT 20
""")

orders_by_hour = q("""
    SELECT order_hour_of_day AS hour,
           COUNT(*) AS order_count
    FROM orders
    GROUP BY order_hour_of_day
    ORDER BY hour
""")

orders_by_dow = q("""
    SELECT order_dow AS day_of_week,
           COUNT(*) AS order_count
    FROM orders
    GROUP BY order_dow
    ORDER BY day_of_week
""")
orders_by_dow['day_name'] = orders_by_dow['day_of_week'].map({
    0:'Sunday',1:'Monday',2:'Tuesday',3:'Wednesday',
    4:'Thursday',5:'Friday',6:'Saturday'
})

basket = pd.read_csv("data/processed/market_basket_rules.csv")
basket['antecedents'] = basket['antecedents'].astype(str).str.strip("frozenset({})'")
basket['consequents'] = basket['consequents'].astype(str).str.strip("frozenset({})'")
basket = basket.head(15)

total_orders   = q("SELECT COUNT(DISTINCT order_id) AS n FROM orders")['n'][0]
total_customers= q("SELECT COUNT(DISTINCT user_id) AS n FROM orders")['n'][0]
total_products = q("SELECT COUNT(DISTINCT product_id) AS n FROM products")['n'][0]
reorder_rate   = q("SELECT ROUND(AVG(reordered)*100,1) AS r FROM order_products")['r'][0]

# ── COLORS ────────────────────────────────────────────────────
BLUE   = '#1155CC'
ORANGE = '#D4621A'
DARK   = '#1a1a1a'
MUTED  = '#6b7280'
LIGHT  = '#f8fafc'
GRID   = '#e5e7eb'

SEG_COLORS = {
    'Champions':         '#1155CC',
    'Loyal Customers':   '#2563eb',
    'New Customers':     '#10b981',
    'At Risk':           '#ef4444',
    'Hibernating / Lost':'#9ca3af',
}

# ── CHARTS ────────────────────────────────────────────────────
def chart_layout(fig, h=340):
    fig.update_layout(
        plot_bgcolor=LIGHT, paper_bgcolor='white',
        font=dict(family='Inter, Arial', color=DARK, size=11),
        margin=dict(l=40, r=20, t=40, b=40),
        height=h,
        legend=dict(bgcolor='rgba(0,0,0,0)'),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig

# RFM bar
fig_rfm = px.bar(
    rfm, x='customer_segment', y='customer_count',
    color='customer_segment',
    color_discrete_map=SEG_COLORS,
    text='customer_count',
    title='Customer Segments — 206K Users',
)
fig_rfm.update_traces(textposition='outside', textfont_size=11)
fig_rfm = chart_layout(fig_rfm)

# Department purchases
fig_dept = px.bar(
    dept.sort_values('total_purchases'),
    x='total_purchases', y='department',
    orientation='h',
    color='reorder_rate',
    color_continuous_scale=[[0,'#dbeafe'],[1,BLUE]],
    text='total_purchases',
    title='Department Performance & Reorder Rate',
)
fig_dept.update_traces(textposition='outside', textfont_size=10)
fig_dept = chart_layout(fig_dept, h=420)

# Orders by hour
fig_hour = px.area(
    orders_by_hour, x='hour', y='order_count',
    title='Order Volume by Hour of Day',
    color_discrete_sequence=[BLUE],
)
fig_hour.update_traces(fill='tozeroy', fillcolor='rgba(17,85,204,0.1)')
fig_hour = chart_layout(fig_hour)

# Orders by day
fig_dow = px.bar(
    orders_by_dow, x='day_name', y='order_count',
    title='Order Volume by Day of Week',
    color='order_count',
    color_continuous_scale=[[0,'#dbeafe'],[1,BLUE]],
    text='order_count',
)
fig_dow.update_traces(textposition='outside', textfont_size=10)
fig_dow = chart_layout(fig_dow)

# Top products
fig_prod = px.bar(
    top_products.sort_values('purchase_count'),
    x='purchase_count', y='product_name',
    orientation='h',
    color='reorder_rate',
    color_continuous_scale=[[0,'#fef3c7'],[1,ORANGE]],
    title='Top 20 Products by Purchase Volume',
)
fig_prod = chart_layout(fig_prod, h=480)

# Market basket scatter
fig_basket = px.scatter(
    basket,
    x='support', y='confidence',
    size='lift', color='lift',
    color_continuous_scale=[[0,MUTED],[1,ORANGE]],
    hover_data=['antecedents','consequents','lift'],
    title='Association Rules — Support vs Confidence (size = Lift)',
)
fig_basket = chart_layout(fig_basket)

# ── KPI CARD ──────────────────────────────────────────────────
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
    style={'borderBottom':f'3px solid {BLUE}','padding':'12px 0'}
)

TABS = dbc.Tabs([

    # ── TAB 1: EXECUTIVE OVERVIEW ──────────────────────────────
    dbc.Tab(label='📊 Executive Overview', children=[
        html.Br(),
        dbc.Row([
            kpi('Total Orders',    f"{int(total_orders):,}"),
            kpi('Unique Customers',f"{int(total_customers):,}"),
            kpi('Products',        f"{int(total_products):,}"),
            kpi('Reorder Rate',    f"{reorder_rate}%", ORANGE),
        ], className='g-3 mb-4'),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(
                dcc.Graph(figure=fig_hour, config={'displayModeBar':False})
            ), style={'borderRadius':'12px','border':f'1px solid {GRID}'}), md=7),
            dbc.Col(dbc.Card(dbc.CardBody(
                dcc.Graph(figure=fig_dow, config={'displayModeBar':False})
            ), style={'borderRadius':'12px','border':f'1px solid {GRID}'}), md=5),
        ], className='g-3'),
    ], tab_style={'padding':'8px 20px'}),

    # ── TAB 2: CUSTOMER ANALYTICS ─────────────────────────────
    dbc.Tab(label='👥 Customer Analytics', children=[
        html.Br(),
        dbc.Row([
            kpi('Champions',        f"{rfm[rfm['customer_segment']=='Champions']['customer_count'].sum():,}", BLUE),
            kpi('Loyal Customers',  f"{rfm[rfm['customer_segment']=='Loyal Customers']['customer_count'].sum():,}", '#2563eb'),
            kpi('At Risk',          f"{rfm[rfm['customer_segment']=='At Risk']['customer_count'].sum():,}", '#ef4444'),
            kpi('Hibernating/Lost', f"{rfm[rfm['customer_segment']=='Hibernating / Lost']['customer_count'].sum():,}", MUTED),
        ], className='g-3 mb-4'),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(
                dcc.Graph(figure=fig_rfm, config={'displayModeBar':False})
            ), style={'borderRadius':'12px','border':f'1px solid {GRID}'}), md=8),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Segment Breakdown",
                        style={'fontWeight':'600','marginBottom':'16px'}),
                dash_table.DataTable(
                    data=rfm.to_dict('records'),
                    columns=[
                        {'name':'Segment',    'id':'customer_segment'},
                        {'name':'Customers',  'id':'customer_count'},
                        {'name':'Avg Orders', 'id':'avg_orders'},
                        {'name':'Avg Items',  'id':'avg_items'},
                    ],
                    style_table={'overflowX':'auto'},
                    style_cell={'fontFamily':'Inter, Arial','fontSize':'12px',
                                'padding':'8px 12px','border':f'1px solid {GRID}'},
                    style_header={'backgroundColor':DARK,'color':'white',
                                  'fontWeight':'600','fontSize':'11px'},
                    style_data_conditional=[
                        {'if':{'filter_query':'{customer_segment} = "Champions"'},
                         'backgroundColor':'#dbeafe','color':BLUE,'fontWeight':'600'},
                        {'if':{'filter_query':'{customer_segment} = "At Risk"'},
                         'backgroundColor':'#fee2e2','color':'#ef4444'},
                    ],
                )
            ]), style={'borderRadius':'12px','border':f'1px solid {GRID}'}), md=4),
        ], className='g-3'),
    ], tab_style={'padding':'8px 20px'}),

    # ── TAB 3: PRODUCT & CATEGORY ─────────────────────────────
    dbc.Tab(label='📦 Product & Category', children=[
        html.Br(),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(
                dcc.Graph(figure=fig_dept, config={'displayModeBar':False})
            ), style={'borderRadius':'12px','border':f'1px solid {GRID}'}), md=5),
            dbc.Col(dbc.Card(dbc.CardBody(
                dcc.Graph(figure=fig_prod, config={'displayModeBar':False})
            ), style={'borderRadius':'12px','border':f'1px solid {GRID}'}), md=7),
        ], className='g-3'),
    ], tab_style={'padding':'8px 20px'}),

    # ── TAB 4: MARKET BASKET ──────────────────────────────────
    dbc.Tab(label='🛒 Market Basket Analysis', children=[
        html.Br(),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody(
                dcc.Graph(figure=fig_basket, config={'displayModeBar':False})
            ), style={'borderRadius':'12px','border':f'1px solid {GRID}'}), md=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Top Association Rules",
                        style={'fontWeight':'600','marginBottom':'16px'}),
                dash_table.DataTable(
                    data=basket[['antecedents','consequents',
                                 'support','confidence','lift']].round(4).to_dict('records'),
                    columns=[
                        {'name':'If customer buys...',  'id':'antecedents'},
                        {'name':'They also buy...',      'id':'consequents'},
                        {'name':'Support',               'id':'support'},
                        {'name':'Confidence',            'id':'confidence'},
                        {'name':'Lift',                  'id':'lift'},
                    ],
                    style_table={'overflowX':'auto'},
                    style_cell={'fontFamily':'Inter, Arial','fontSize':'11px',
                                'padding':'7px 10px','border':f'1px solid {GRID}',
                                'maxWidth':'160px','overflow':'hidden',
                                'textOverflow':'ellipsis'},
                    style_header={'backgroundColor':DARK,'color':'white',
                                  'fontWeight':'600','fontSize':'11px'},
                    sort_action='native',
                    filter_action='native',
                )
            ]), style={'borderRadius':'12px','border':f'1px solid {GRID}'}), md=6),
        ], className='g-3'),
    ], tab_style={'padding':'8px 20px'}),

], style={'marginTop':'8px'})

app.layout = dbc.Container([
    NAV,
    html.Br(),
    TABS,
    html.Br(),
    html.Hr(style={'borderColor':GRID}),
    html.P(
        "Instacart Intelligence Platform · 3.4M Orders · 206K Customers · "
        "50K+ Products · Built with Python, PostgreSQL, Plotly Dash",
        className='text-center text-muted',
        style={'fontSize':'0.72rem','letterSpacing':'0.08em'}
    ),
], fluid=True, style={'backgroundColor':LIGHT,'minHeight':'100vh','padding':'0'})

if __name__ == '__main__':
    app.run(debug=True, port=8050)