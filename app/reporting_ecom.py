import os, json
from decimal import Decimal
from datetime import datetime, timedelta, date
from sqlalchemy import text
from .db import get_session

def _margins():
    d = json.loads(os.getenv("BRAND_MARGINS_UAH","{}"))
    return {str(k): Decimal(str(v)) for k,v in d.items()}, Decimal(str(os.getenv("DEFAULT_MARGIN_UAH","0.3")))

def _range_for_day(day: date, tz="Europe/Kyiv"):
    from zoneinfo import ZoneInfo
    start = datetime.combine(day, datetime.min.time()).replace(tzinfo=ZoneInfo(tz))
    end = start + timedelta(days=1)
    return start, end

def daily_kpis_for_day(day: date):
    margins, default_m = _margins()
    start, end = _range_for_day(day)
    sess = get_session()

    cost_rows = sess.execute(text("""
        SELECT campaign, SUM(cost) AS cost, SUM(clicks) AS clicks, SUM(impressions) AS impressions
        FROM ad_stats
        WHERE stat_date = :d
        GROUP BY campaign
    """), {"d": day}).fetchall()
    kpis = {}
    for camp, cost, clicks, imp in cost_rows:
        kpis[camp] = {
            "cost": Decimal(str(cost or 0)),
            "clicks": int(clicks or 0),
            "impressions": int(imp or 0),
            "revenue": Decimal("0"),
            "profit": Decimal("0"),
            "orders": 0,
            "margin_eff": Decimal("0")
        }

    order_rows = sess.execute(text("""
        SELECT utm_campaign, amount_uah, brand
        FROM orders
        WHERE created_at >= :start AND created_at < :end
    """), {"start": start, "end": end}).fetchall()

    rev_by_camp = {}; prof_by_camp = {}; cnt_by_camp = {}; margin_sum_by_camp = {}

    for camp, amt, br in order_rows:
        camp = camp or "unknown"
        amt = Decimal(str(amt or 0))
        m = margins.get(str(br), default_m)
        rev_by_camp[camp] = rev_by_camp.get(camp, Decimal("0")) + amt
        prof_by_camp[camp] = prof_by_camp.get(camp, Decimal("0")) + (amt * m)
        cnt_by_camp[camp] = cnt_by_camp.get(camp, 0) + 1
        margin_sum_by_camp[camp] = margin_sum_by_camp.get(camp, Decimal("0")) + m

    for camp in set(list(kpis.keys()) + list(rev_by_camp.keys())):
        if camp not in kpis:
            kpis[camp] = {"cost": Decimal("0"), "clicks": 0, "impressions": 0,
                          "revenue": Decimal("0"), "profit": Decimal("0"), "orders": 0, "margin_eff": Decimal("0")}
        kpis[camp]["revenue"] = rev_by_camp.get(camp, Decimal("0"))
        gross_profit = prof_by_camp.get(camp, Decimal("0"))
        kpis[camp]["profit"] = gross_profit - kpis[camp]["cost"]
        kpis[camp]["orders"] = cnt_by_camp.get(camp, 0)
        if cnt_by_camp.get(camp):
            kpis[camp]["margin_eff"] = margin_sum_by_camp[camp] / Decimal(cnt_by_camp[camp])

    return kpis

from decimal import Decimal as D

def _ctr(clicks:int, imp:int) -> D:
    return (D(clicks)/D(imp)*D(100)) if imp>0 else D(0)

def recommend(k:dict):
    cost, rev, orders = k["cost"], k["revenue"], k["orders"]
    clicks, imp = k["clicks"], k["impressions"]
    roas = (rev/cost) if cost>0 else D(0)
    ctr = _ctr(clicks, imp)

    if cost>0 and roas > D("3"):
        return "Підняти денний бюджет на +20% (є вільний потенціал)", "good"
    if cost>0 and D("1.5") <= roas <= D("3"):
        return "Залишити без змін", "ok"
    if cost>0 and roas < D("1.5") and orders < 5:
        return "Зменшити бюджет на -20%", "warn"
    if cost>0 and roas < D("1") and orders > 10:
        return "Переглянути ціни або фото (проблема в маржі/конверсії)", "bad"
    if orders == 0 and clicks > 100:
        return "Вимкнути рекламу цієї кампанії/товару", "bad"
    if ctr < D("2"):
        return "Низький CTR (<2%) — оновити оголошення/креатив", "warn"
    return "Недостатньо даних — спостерігаємо", "neutral"

from datetime import date as _date

def build_daily_message(day: _date):
    kpis = daily_kpis_for_day(day)
    currency = os.getenv("CURRENCY","UAH")
    lines = [f"📊 Щоденний звіт ({day.strftime('%d %B')})"]
    for camp, v in sorted(kpis.items(), key=lambda kv: kv[1]["revenue"], reverse=True):
        cost, rev = v["cost"], v["revenue"]
        roas = (rev/cost) if cost>0 else D(0)
        payback = ((v["profit"]/cost)*D(100)) if cost>0 else D(0)
        rec, tag = recommend(v)
        lines += [
            "",
            f"Кампанія: {camp}",
            f"Витрати: {cost:.0f} {currency}",
            f"Виручка: {rev:.0f} {currency}",
            f"Маржа (ефект.): {int(v['margin_eff']*100) if v['margin_eff'] else '-'}%",
            f"Чистий прибуток: {v['profit']:.0f} {currency} {'✅' if v['profit']>0 else '❌'}",
            f"ROAS: {roas:.2f}",
            f"Окупність: {payback:.0f}%" if cost>0 else "Окупність: –",
            f"Кліки: {v['clicks']}, Покази: {v['impressions']}, Замовлень: {v['orders']}",
            f"💡 Рекомендація: {rec}",
        ]
    return "\n".join(lines)
