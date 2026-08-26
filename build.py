"""根据领星多平台订单 JSON 生成静态 HTML 仪表盘"""
import json, os, html, io, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "output", "multiplatform_orders.json")
OUT_PATH = os.path.join(HERE, "index.html")

PLATFORM_META = {
    "10012": {"short": "美客多", "full": "MercadoLibre 美客多", "color": "#FFE600"},
}

# eMAG / 沃尔玛 目前领星无数据，作为占位展示
EXTRA_PLATFORMS = [
    {"code": "eMAG", "short": "eMAG", "full": "eMAG", "has_data": False},
    {"code": "WMT", "short": "沃尔玛", "full": "Walmart 沃尔玛", "has_data": False},
]


def load():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def build(data):
    pull_time = data.get("pull_time", "")
    days = data.get("days", 7)
    platforms = data.get("platforms", {})
    # 只渲染有数据的平台
    active_codes = [c for c in platforms if platforms[c].get("order_count", 0) > 0]

    sections = []
    for code in active_codes:
        p = platforms[code]
        meta = PLATFORM_META.get(code, {"short": code, "full": code, "color": "#333"})
        sections.append(render_platform(code, p, meta, pull_time, days))

    # 汇总卡片顶部
    total_orders = sum(p.get("order_count", 0) for p in platforms.values())
    cards = f"""
    <div class="kpis">
      <div class="kpi"><div class="kpi-num">{total_orders}</div><div class="kpi-label">近{days}天订单总数</div></div>
      <div class="kpi"><div class="kpi-num">{round(total_orders / max(days, 1), 1)}</div><div class="kpi-label">日均订单</div></div>
      <div class="kpi"><div class="kpi-num">{len(active_codes)}</div><div class="kpi-label">有数据平台</div></div>
      <div class="kpi"><div class="kpi-num">{sum(len(p.get('stores', {})) for p in platforms.values())}</div><div class="kpi-label">平台店铺总数</div></div>
    </div>
    """

    # 平台状态条
    chips = []
    for c in active_codes:
        meta = PLATFORM_META.get(c, {})
        chips.append(f'<span class="chip on" style="border-color:{meta.get("color","#333")}">{meta.get("short", c)} 有数据</span>')
    for ep in EXTRA_PLATFORMS:
        chips.append(f'<span class="chip off">{ep["short"]} 领星暂无数据</span>')
    chip_html = '<div class="chips">' + "".join(chips) + "</div>"

    body = "".join(sections)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>多平台每日订单看板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Microsoft YaHei", "PingFang SC", -apple-system, sans-serif; background: #f4f6f9; color: #1f2430; padding: 16px; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  header {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
  header h1 {{ font-size: 22px; color: #1f2430; }}
  .time {{ color: #6b7280; font-size: 13px; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
  .chip {{ padding: 5px 12px; border-radius: 999px; font-size: 13px; border: 2px solid transparent; }}
  .chip.on {{ background: #fff; font-weight: 600; }}
  .chip.off {{ background: #e5e7eb; color: #6b7280; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 18px; }}
  .kpi {{ background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  .kpi-num {{ font-size: 26px; font-weight: 700; }}
  .kpi-label {{ font-size: 12px; color: #6b7280; margin-top: 4px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.06); margin-bottom: 18px; }}
  .card h2 {{ font-size: 16px; margin-bottom: 12px; }}
  .chart-box {{ position: relative; height: 320px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ border: 1px solid #e5e7eb; padding: 7px 6px; text-align: center; }}
  th {{ background: #f9fafb; font-weight: 600; }}
  td.store {{ text-align: left; }}
  tr.total td {{ font-weight: 700; background: #fffbe6; }}
  .foot {{ color: #9ca3af; font-size: 12px; text-align: center; margin-top: 18px; }}
  @media (max-width: 640px) {{ header h1 {{ font-size: 18px; }} .chart-box {{ height: 240px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>多平台每日订单看板</h1>
    <div class="time">数据更新时间：{html.escape(pull_time)}</div>
  </header>
  {chip_html}
  {cards}
  {body}
  <div class="foot">数据来源：领星 ERP OpenAPI · 按订单下单时间(北京时区)统计 · 由脚本自动生成</div>
</div>
</body>
</html>
"""


def render_platform(code, p, meta, pull_time, days):
    short = meta["short"]
    full = meta["full"]
    color = meta["color"]

    daily = p["daily_total"]
    valid = p["daily_valid"]
    amount = p["daily_amount"]
    store_daily = p["store_daily"]
    stores = p["stores"]

    dates = sorted(daily.keys())
    # 若跨天不全，按最近N天补0，只保留最近N个自然日
    if dates:
        try:
            from datetime import date, timedelta
            ref = date.fromisoformat(dates[-1])
            all_dates = [(ref - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
            for d in all_dates:
                if d not in daily:
                    daily[d] = 0
                    valid[d] = 0
                    amount[d] = {}
            dates = all_dates
        except Exception:
            pass

    labels = [d[5:] for d in dates]  # MM-DD
    totals = [daily.get(d, 0) for d in dates]
    valids = [valid.get(d, 0) for d in dates]

    amt_lines = []
    for d in dates:
        parts = []
        for cur, v in sorted(amount.get(d, {}).items()):
            parts.append(f"{cur} {v:,.2f}")
        amt_lines.append("<br>".join(parts) if parts else "—")

    # 店铺表
    sids = [sid for sid in store_daily if sum(store_daily[sid].values()) > 0]
    sids.sort(key=lambda sid: -sum(store_daily[sid].values()))

    thead = "<tr><th class='store'>店铺</th>" + "".join(f"<th>{d[5:]}</th>" for d in dates) + "<th>合计</th></tr>"
    trows = []
    for sid in sids:
        dd = store_daily[sid]
        name = stores.get(sid, sid)
        row = "<tr><td class='store'>" + html.escape(name) + "</td>"
        for d in dates:
            row += f"<td>{dd.get(d, 0)}</td>"
        row += f"<td>{sum(dd.values())}</td></tr>"
        trows.append(row)
    col_totals = "".join(f"<td>{sum(store_daily[s].get(d, 0) for s in sids)}</td>" for d in dates)
    total_row = f"<tr class='total'><td>合计</td>{col_totals}<td>{sum(totals)}</td></tr>"
    table = thead + "".join(trows) + total_row

    # 金额行
    amt_thead = "<tr><th class='store'>日期</th><th>订单数</th><th>有效订单</th><th>销售额(原币种)</th></tr>"
    amt_rows = []
    for i, d in enumerate(dates):
        amt_rows.append(
            f"<tr><td class='store'>{d}</td><td>{totals[i]}</td><td>{valids[i]}</td><td>{amt_lines[i]}</td></tr>"
        )
    amt_table = amt_thead + "".join(amt_rows)

    total_orders = p.get("order_count", 0)

    # Chart.js 配置（转义 JSON）
    chart_id = "chart_" + code
    labels_json = json.dumps(labels)
    totals_json = json.dumps(totals)

    return f"""
  <div class="card">
    <h2>{short} · {full}
      <span style="font-size:12px;color:#6b7280;font-weight:400;margin-left:8px;">7天共 {total_orders} 单 · {len(sids)} 家有单店铺</span>
    </h2>
    <div class="chart-box"><canvas id="{chart_id}"></canvas></div>
  </div>

  <div class="card">
    <h2>{short} · 各店铺每日订单</h2>
    <div style="overflow-x:auto;"><table>{table}</table></div>
  </div>

  <div class="card">
    <h2>{short} · 每日订单与销售额</h2>
    <div style="overflow-x:auto;"><table>{amt_table}</table></div>
  </div>

  <script>
  (function(){{
    var ctx = document.getElementById('{chart_id}');
    if(!ctx || typeof Chart === 'undefined') return;
    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: {labels_json},
        datasets: [{{
          label: '订单数',
          data: {totals_json},
          backgroundColor: '{color}',
          borderColor: '#00000022',
          borderWidth: 1,
          borderRadius: 6,
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ callbacks: {{ label: function(c){{ return c.parsed.y + ' 单'; }} }} }}
        }},
        scales: {{
          y: {{ beginAtZero: true, ticks: {{ precision: 0 }} }}
        }}
      }}
    }});
  }})();
  </script>
"""


def main():
    data = load()
    html_out = build(data)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"generated: {OUT_PATH}")
    print(f"platforms with data: {[c for c,p in data['platforms'].items() if p.get('order_count',0)>0]}")


if __name__ == "__main__":
    main()
