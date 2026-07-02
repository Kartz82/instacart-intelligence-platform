import dash
from dash import dcc, html, dash_table
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

_RFM_FALLBACK_CACHE = None

# ── CONNECTION ────────────────────────────────────────────────
ENGINE = create_engine(
    "postgresql://postgres:postgres@localhost:5434/instacart_db"
)

def _pg_ntile(values, sort_frame, sort_columns, ascending, buckets=5):
    n = len(values)
    base_size, remainder = divmod(n, buckets)
    tiles = []
    for bucket in range(1, buckets + 1):
        tiles.extend([bucket] * (base_size + (1 if bucket <= remainder else 0)))

    ordered_index = sort_frame.sort_values(
        sort_columns,
        ascending=ascending,
        kind="mergesort",
    ).index
    return pd.Series(tiles, index=ordered_index).sort_index()


def _rfm_segments_from_raw_csv():
    """Computed export fallback; mirrors sql/rfm_analysis.sql without hardcoded counts."""
    global _RFM_FALLBACK_CACHE
    if _RFM_FALLBACK_CACHE is not None:
        return _RFM_FALLBACK_CACHE.copy()

    orders = pd.read_csv(
        "data/raw/orders.csv",
        usecols=["order_id", "user_id", "order_number", "days_since_prior_order"],
    )
    latest_orders = (
        orders.sort_values(["user_id", "order_number", "order_id"])
        .groupby("user_id", as_index=False)
        .tail(1)[["user_id", "order_id", "order_number", "days_since_prior_order"]]
        .rename(columns={
            "order_id": "latest_order_id",
            "order_number": "latest_order_number",
            "days_since_prior_order": "latest_reorder_gap_days",
        })
    )
    customer_metrics = (
        orders.groupby("user_id", as_index=False)
        .agg(total_orders=("order_id", "nunique"))
        .merge(latest_orders, on="user_id", how="left")
    )

    order_to_user = orders.set_index("order_id")["user_id"]
    item_totals = {}
    for chunk in pd.read_csv("data/raw/order_products.csv", usecols=["order_id"], chunksize=2_000_000):
        user_ids = chunk["order_id"].map(order_to_user)
        for user_id, count in user_ids.value_counts(sort=False).items():
            item_totals[int(user_id)] = item_totals.get(int(user_id), 0) + int(count)

    item_metrics = pd.DataFrame({
        "user_id": list(item_totals.keys()),
        "total_items_purchased": list(item_totals.values()),
    })
    customer_metrics = customer_metrics.merge(item_metrics, on="user_id", how="left")
    customer_metrics["total_items_purchased"] = customer_metrics["total_items_purchased"].fillna(0).astype(int)
    customer_metrics["avg_items_per_order"] = (
        customer_metrics["total_items_purchased"] / customer_metrics["total_orders"]
    ).round(2)

    customer_metrics["recency_gap_sort"] = customer_metrics["latest_reorder_gap_days"].fillna(999999.0)
    customer_metrics["recency_score"] = 6 - _pg_ntile(
        customer_metrics["recency_gap_sort"],
        customer_metrics,
        ["recency_gap_sort", "user_id"],
        [True, True],
    )
    customer_metrics["frequency_score"] = _pg_ntile(
        customer_metrics["total_orders"],
        customer_metrics,
        ["total_orders", "user_id"],
        [True, True],
    )
    customer_metrics["value_score"] = _pg_ntile(
        customer_metrics["total_items_purchased"],
        customer_metrics,
        ["total_items_purchased", "user_id"],
        [True, True],
    )
    customer_metrics["rfm_score"] = (
        customer_metrics["recency_score"]
        + customer_metrics["frequency_score"]
        + customer_metrics["value_score"]
    )

    customer_metrics["customer_segment"] = "Loyal Customers"
    customer_metrics.loc[customer_metrics["rfm_score"] >= 13, "customer_segment"] = "Champions"
    customer_metrics.loc[customer_metrics["rfm_score"] <= 5, "customer_segment"] = "Hibernating / Lost"
    customer_metrics.loc[
        (customer_metrics["recency_score"] <= 3)
        & (customer_metrics["rfm_score"].between(6, 9)),
        "customer_segment",
    ] = "At Risk"
    customer_metrics.loc[
        (customer_metrics["frequency_score"] <= 2)
        & (customer_metrics["recency_score"] >= 4),
        "customer_segment",
    ] = "New Customers"

    _RFM_FALLBACK_CACHE = customer_metrics
    return customer_metrics.copy()


def _fallback_query(sql):
    """Local CSV fallback used only for static portfolio exports."""
    query = " ".join(sql.lower().split())

    if "from customer_rfm_segments" in query:
        source = _rfm_segments_from_raw_csv()
        return (
            source.groupby("customer_segment", as_index=False)
            .agg(
                customer_count=("user_id", "count"),
                avg_orders=("total_orders", "mean"),
                avg_items=("total_items_purchased", "mean"),
            )
            .round({"avg_orders": 1, "avg_items": 1})
            .sort_values("customer_count", ascending=False)
            .reset_index(drop=True)
        )

    if "from order_products op" in query and "join departments" in query:
        products = pd.read_csv("data/raw/products.csv", usecols=["product_id", "department_id"])
        departments = pd.read_csv("data/raw/departments.csv")
        product_dept = products.merge(departments, on="department_id", how="left")
        product_dept = product_dept.set_index("product_id")["department"]

        totals = {}
        reorders = {}
        for chunk in pd.read_csv(
            "data/raw/order_products.csv",
            usecols=["product_id", "reordered"],
            chunksize=1_000_000,
        ):
            chunk["department"] = chunk["product_id"].map(product_dept)
            grouped = chunk.groupby("department")["reordered"].agg(["count", "sum"])
            for department, row in grouped.iterrows():
                totals[department] = totals.get(department, 0) + int(row["count"])
                reorders[department] = reorders.get(department, 0) + int(row["sum"])

        df = pd.DataFrame({
            "department": list(totals.keys()),
            "total_purchases": list(totals.values()),
        })
        df["reorder_rate"] = df["department"].map(
            lambda d: round(reorders.get(d, 0) / totals[d], 3)
        )
        return df.sort_values("total_purchases", ascending=False).head(15).reset_index(drop=True)

    if "from order_products op" in query and "join products" in query:
        products = pd.read_csv("data/raw/products.csv", usecols=["product_id", "product_name"])
        product_names = products.set_index("product_id")["product_name"]

        totals = {}
        reorders = {}
        for chunk in pd.read_csv(
            "data/raw/order_products.csv",
            usecols=["product_id", "reordered"],
            chunksize=1_000_000,
        ):
            grouped = chunk.groupby("product_id")["reordered"].agg(["count", "sum"])
            for product_id, row in grouped.iterrows():
                product_id = int(product_id)
                totals[product_id] = totals.get(product_id, 0) + int(row["count"])
                reorders[product_id] = reorders.get(product_id, 0) + int(row["sum"])

        df = pd.DataFrame({
            "product_id": list(totals.keys()),
            "purchase_count": list(totals.values()),
        })
        df["product_name"] = df["product_id"].map(product_names)
        df["reorder_rate"] = df["product_id"].map(
            lambda product_id: round(reorders.get(product_id, 0) / totals[product_id], 3)
        )
        return (
            df.dropna(subset=["product_name"])
            .sort_values("purchase_count", ascending=False)
            .head(20)
            .reset_index(drop=True)
        )

    if "order_hour_of_day" in query:
        orders = pd.read_csv("data/raw/orders.csv", usecols=["order_hour_of_day"])
        return (
            orders.groupby("order_hour_of_day")
            .size()
            .reset_index(name="order_count")
            .rename(columns={"order_hour_of_day": "hour"})
            .sort_values("hour")
        )

    if "order_dow" in query:
        orders = pd.read_csv("data/raw/orders.csv", usecols=["order_dow"])
        return (
            orders.groupby("order_dow")
            .size()
            .reset_index(name="order_count")
            .rename(columns={"order_dow": "day_of_week"})
            .sort_values("day_of_week")
        )

    if "count(distinct order_id)" in query:
        orders = pd.read_csv("data/raw/orders.csv", usecols=["order_id"])
        return pd.DataFrame({"n": [orders["order_id"].nunique()]})

    if "count(distinct user_id)" in query:
        orders = pd.read_csv("data/raw/orders.csv", usecols=["user_id"])
        return pd.DataFrame({"n": [orders["user_id"].nunique()]})

    if "count(distinct product_id)" in query:
        products = pd.read_csv("data/raw/products.csv", usecols=["product_id"])
        return pd.DataFrame({"n": [products["product_id"].nunique()]})

    if "avg(reordered)" in query:
        total_rows = 0
        total_reorders = 0
        for chunk in pd.read_csv("data/raw/order_products.csv", usecols=["reordered"], chunksize=1_000_000):
            total_rows += len(chunk)
            total_reorders += int(chunk["reordered"].sum())
        return pd.DataFrame({"r": [round((total_reorders / total_rows) * 100, 1)]})

    raise RuntimeError("No local CSV fallback is available for this query.")

def q(sql):
    try:
        return pd.read_sql(sql, ENGINE)
    except Exception:
        if EXPORT_MODE:
            return _fallback_query(sql)
        raise

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
            colorscale=[
                [0.00, PORTFOLIO_BLUE],
                [0.45, PORTFOLIO_TEAL],
                [0.75, PORTFOLIO_AMBER],
                [1.00, PORTFOLIO_ROSE],
            ],
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
            colorscale=[
                [0.00, PORTFOLIO_BLUE],
                [0.50, PORTFOLIO_TEAL],
                [1.00, PORTFOLIO_GREEN],
            ],
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
    segment_order = [
        "Hibernating / Lost",
        "At Risk",
        "Loyal Customers",
        "New Customers",
        "Champions",
    ]
    segment_colors = {
        "Champions": PORTFOLIO_BLUE,
        "Loyal Customers": PORTFOLIO_BLUE,
        "At Risk": PORTFOLIO_ROSE,
        "Hibernating / Lost": PORTFOLIO_GRAY,
        "New Customers": PORTFOLIO_TEAL,
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
        app.run(debug=True, port=8050)
