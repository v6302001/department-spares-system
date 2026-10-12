import os
import io
import csv
import hmac
import shutil
import json
import psycopg
from psycopg.rows import dict_row
import hashlib
import secrets
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
OUTPUT_DIR = APP_DIR / "output"
BACKUP_DIR = Path(os.environ.get("SPARES_BACKUP_DIR", str(APP_DIR / "backups"))).expanduser()
for folder in (OUTPUT_DIR, BACKUP_DIR):
    folder.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="部門備品管理系統", page_icon="📦", layout="wide")

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def connect():
    required = ["SPARES_PG_HOST", "SPARES_PG_PORT", "SPARES_PG_DATABASE",
                "SPARES_PG_USER", "SPARES_PG_PASSWORD"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(
            "缺少 PostgreSQL 連線環境變數：" + ", ".join(missing) +
            "。請先設定 SPARES_PG_HOST、SPARES_PG_PORT、SPARES_PG_DATABASE、"
            "SPARES_PG_USER、SPARES_PG_PASSWORD。"
        )
    return psycopg.connect(
        host=os.environ["SPARES_PG_HOST"],
        port=os.environ["SPARES_PG_PORT"],
        dbname=os.environ["SPARES_PG_DATABASE"],
        user=os.environ["SPARES_PG_USER"],
        password=os.environ["SPARES_PG_PASSWORD"],
        sslmode=os.environ.get("SPARES_PG_SSLMODE", "require"),
        row_factory=dict_row,
        connect_timeout=15,
        options="-c search_path=spares,public",
    )


def query_df(query, con, params=None):
    """Run a PostgreSQL query and return a pandas DataFrame."""
    with con.cursor() as cur:
        cur.execute(query, params or ())
        rows = cur.fetchall()
        columns = [item.name for item in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=columns)

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 240000).hex()
    return salt, digest

def verify_password(password, salt, digest):
    _, check = hash_password(password, salt)
    return hmac.compare_digest(check, digest)

def init_db():
    # PostgreSQL schema/data are provisioned separately. Never create a default
    # administrator or silently initialize an empty production database here.
    required_tables = {"users", "staff", "items", "movements", "audit_log"}
    with connect() as con:
        with con.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'spares'
                  AND table_name = ANY(%s)
            """, (list(required_tables),))
            found = {row["table_name"] for row in cur.fetchall()}
            missing = required_tables - found
            if missing:
                raise RuntimeError(
                    "Supabase spares schema 缺少資料表：" + ", ".join(sorted(missing))
                )
            cur.execute("SELECT COUNT(*) AS n FROM spares.users")
            if cur.fetchone()["n"] == 0:
                raise RuntimeError(
                    "雲端 users 表沒有管理員帳號。請先確認資料遷移，不會自動建立預設帳號。"
                )

def log_action(username, action, detail):
    with connect() as con:
        con.execute("INSERT INTO audit_log(created_at,username,action,detail) VALUES(%s,%s,%s,%s)",
                    (now_str(), username, action, str(detail)))
        con.commit()

def current_stock(con, item_id):
    row = con.execute("""
        SELECT i.opening_qty + COALESCE(SUM(
            CASE WHEN m.movement_type IN ('入庫','盤點增加') THEN m.qty
                 WHEN m.movement_type IN ('出庫','盤點減少') THEN -m.qty ELSE 0 END
        ),0) AS qty
        FROM items i LEFT JOIN movements m ON m.item_id=i.id
        WHERE i.id=%s GROUP BY i.id
    """, (item_id,)).fetchone()
    return float(row["qty"] or 0)

def stock_df():
    with connect() as con:
        return query_df("""
            SELECT i.id,i.code AS 備品編號,i.name AS 備品名稱,i.specification AS 規格,
                   i.category AS 類別,i.unit AS 單位,i.location AS 儲位,
                   i.equipment_id AS 關聯設備編號,i.min_stock AS 最低庫存,
                   i.target_stock AS 目標庫存,i.unit_cost AS 單位成本,
                   i.opening_qty + COALESCE(SUM(
                     CASE WHEN m.movement_type IN ('入庫','盤點增加') THEN m.qty
                          WHEN m.movement_type IN ('出庫','盤點減少') THEN -m.qty ELSE 0 END
                   ),0) AS 目前庫存
            FROM items i LEFT JOIN movements m ON m.item_id=i.id
            WHERE i.active=1
            GROUP BY i.id ORDER BY i.code
        """, con)

def item_options():
    with connect() as con:
        rows = con.execute("SELECT id,code,name,specification,unit FROM items WHERE active=1 ORDER BY code").fetchall()
        return {f"{r['code']} | {r['name']} | {r['specification']}": dict(r) for r in rows}

def require_admin():
    if st.session_state.user["role"] != "admin":
        st.error("此功能僅限管理員使用。")
        st.stop()

def login_screen():
    st.title("📦 部門備品管理系統")
    st.caption("第一版｜共用庫存、異動追蹤、低庫存預警")
    with st.form("login_form"):
        username = st.text_input("登入帳號")
        password = st.text_input("密碼", type="password")
        submitted = st.form_submit_button("登入", use_container_width=True)
    if submitted:
        with connect() as con:
            user = con.execute("SELECT * FROM users WHERE username=%s AND active=1", (username.strip(),)).fetchone()
        if user and verify_password(password, user["salt"], user["password_hash"]):
            st.session_state.user = dict(user)
            log_action(username.strip(), "登入", "登入成功")
            st.rerun()
        else:
            st.error("帳號或密碼錯誤，或帳號已停用。")
    if os.environ.get("SPARES_DB_PATH"):
        st.info("初始管理員帳號：admin；初始密碼由部署時設定。登入後請立即修改密碼，並為每位同仁建立個人帳號。")
    else:
        st.info("首次登入帳號：admin；初始密碼：ChangeMe123!。登入後請立即至「帳號與權限」修改密碼。")

def change_own_password():
    st.subheader("修改我的密碼")
    with st.form("change_password"):
        old = st.text_input("目前密碼", type="password")
        new1 = st.text_input("新密碼（至少 10 個字元）", type="password")
        new2 = st.text_input("再次輸入新密碼", type="password")
        ok = st.form_submit_button("更新密碼")
    if ok:
        u = st.session_state.user
        if not verify_password(old, u["salt"], u["password_hash"]):
            st.error("目前密碼不正確。")
        elif len(new1) < 10:
            st.error("新密碼至少需要 10 個字元。")
        elif new1 != new2:
            st.error("兩次輸入的新密碼不一致。")
        else:
            salt, digest = hash_password(new1)
            with connect() as con:
                con.execute("UPDATE users SET salt=%s,password_hash=%s WHERE id=%s", (salt,digest,u["id"]))
                con.commit()
            st.session_state.user["salt"] = salt
            st.session_state.user["password_hash"] = digest
            log_action(u["username"], "修改密碼", "使用者自行修改密碼")
            st.success("密碼已更新。")

def add_movement(kind, item_id, qty, staff_name, reason, equipment_id="", reference_no="", note=""):
    u = st.session_state.user
    with connect() as con:
        con.execute("BEGIN")
        item = con.execute("SELECT * FROM items WHERE id=%s AND active=1 FOR UPDATE", (item_id,)).fetchone()
        if not item:
            raise ValueError("找不到有效的備品資料。")
        before = current_stock(con, item_id)
        qty = float(qty)
        if qty <= 0:
            raise ValueError("數量必須大於 0。")
        is_out = kind in ("出庫", "盤點減少")
        if is_out and qty > before + 1e-9:
            raise ValueError(f"庫存不足。目前庫存 {before:g} {item['unit']}，不能扣除 {qty:g}。")
        after = before - qty if is_out else before + qty
        con.execute("""INSERT INTO movements(created_at,movement_type,item_id,qty,staff_name,operator_username,
                       reason,equipment_id,reference_no,note,before_qty,after_qty)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (now_str(),kind,item_id,qty,staff_name,u["username"],reason,equipment_id,reference_no,note,before,after))
        con.commit()
    log_action(u["username"], "庫存異動", f"{kind}; item_id={item_id}; qty={qty:g}; {reason}")

def template_xlsx():
    df = pd.DataFrame([{
        "備品編號":"SP-0001","備品名稱":"範例：氣缸","規格":"型號/尺寸","類別":"氣動元件",
        "單位":"個","儲位":"A-01-01","關聯設備編號":"EQ-001","最低庫存":3,
        "目標庫存":10,"單位成本":0,"期初庫存":5
    }])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="備品清單")
    return buf.getvalue()

def normalize_import_columns(df):
    aliases = {
        "備品編號":"code","物料編號":"code","料號":"code","編號":"code","code":"code",
        "備品名稱":"name","品名":"name","名稱":"name","name":"name",
        "規格":"specification","型號":"specification","specification":"specification",
        "類別":"category","分類":"category","category":"category",
        "單位":"unit","計量單位":"unit","unit":"unit",
        "儲位":"location","存放位置":"location","位置":"location","location":"location",
        "關聯設備編號":"equipment_id","設備編號":"equipment_id","equipment_id":"equipment_id",
        "最低庫存":"min_stock","安全庫存":"min_stock","min_stock":"min_stock",
        "目標庫存":"target_stock","目標數量":"target_stock","target_stock":"target_stock",
        "單位成本":"unit_cost","單價":"unit_cost","unit_cost":"unit_cost",
        "期初庫存":"opening_qty","目前庫存":"opening_qty","初始庫存":"opening_qty","opening_qty":"opening_qty"
    }
    rename = {}
    for c in df.columns:
        key = str(c).strip()
        if key in aliases:
            rename[c] = aliases[key]
    return df.rename(columns=rename)

def main_app():
    user = st.session_state.user
    with st.sidebar:
        st.title("📦 備品管理")
        st.write(f"登入：**{user['display_name']}**")
        st.caption("權限：" + ("管理員" if user["role"] == "admin" else "一般操作人員"))
        page = st.radio("功能選單", [
            "總覽儀表板","入庫 / 出庫","庫存查詢","缺少清單","月報與匯出",
            "異動紀錄","備品資料管理","人員管理","帳號與權限","備份與還原"
        ])
        if st.button("登出", use_container_width=True):
            log_action(user["username"], "登出", "使用者登出")
            del st.session_state.user
            st.rerun()

    if page == "總覽儀表板":
        st.title("總覽儀表板")
        df = stock_df()
        if df.empty:
            st.warning("目前沒有備品資料。請管理員到「備品資料管理」匯入 Excel。")
            return
        shortages = df[df["目前庫存"] < df["最低庫存"]]
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("有效備品種類", f"{len(df):,}")
        c2.metric("低於最低庫存", f"{len(shortages):,}")
        c3.metric("庫存總金額", f"{(df['目前庫存']*df['單位成本']).sum():,.2f}")
        c4.metric("目前庫存總數量", f"{df['目前庫存'].sum():,.2f}")
        st.subheader("優先處理的缺料項目")
        if len(shortages):
            view = shortages.copy()
            view["缺少數量"] = (view["最低庫存"] - view["目前庫存"]).clip(lower=0)
            st.dataframe(view[["備品編號","備品名稱","規格","儲位","目前庫存","最低庫存","目標庫存","缺少數量"]].sort_values("目前庫存"), use_container_width=True, hide_index=True)
        else:
            st.success("目前沒有低於最低庫存的備品。")
        st.subheader("最近 10 筆異動")
        with connect() as con:
            recent = query_df("""SELECT m.created_at AS 時間,m.movement_type AS 類型,i.code AS 備品編號,
                i.name AS 備品名稱,m.qty AS 數量,m.staff_name AS "領用/相關人員",m.operator_username AS 操作帳號,
                m.reason AS 原因,m.before_qty AS 異動前,m.after_qty AS 異動後
                FROM movements m JOIN items i ON i.id=m.item_id ORDER BY m.id DESC LIMIT 10""", con)
        st.dataframe(recent, use_container_width=True, hide_index=True)

    elif page == "入庫 / 出庫":
        st.title("入庫 / 出庫")
        opts = item_options()
        if not opts:
            st.warning("請先匯入或建立備品資料。")
            return
        with connect() as con:
            staff = [r["name"] for r in con.execute("SELECT name FROM staff WHERE active=1 ORDER BY name").fetchall()]
        if not staff:
            staff = [user["display_name"]]
        # 搜尋欄位置於表單外，輸入後可立即縮小下拉選單選項；原有下拉選單保留。
        kind = st.radio("異動類型", ["入庫","出庫"], horizontal=True, key="movement_kind")
        search_text = st.text_input("搜尋備品（編號、名稱、規格、儲位或關聯設備）", key="movement_item_search")
        labels = list(opts.keys())
        if search_text.strip():
            needle = search_text.strip().casefold()
            labels = [label for label in labels if needle in " ".join(str(opts[label].get(k, "") or "") for k in
                      ("code", "name", "specification", "location", "equipment_id")).casefold() or needle in label.casefold()]
        if not labels:
            st.warning("沒有符合搜尋條件的備品，請修改搜尋文字。")
            return
        selected = st.selectbox("備品", labels, key="movement_item_select")
        item = opts[selected]
        stock_now = current_stock(connect(), item["id"])
        st.caption(f"目前庫存：{stock_now:g} {item['unit']}")
        # 原因選單與「其他」輸入框放在表單外，選擇「其他」時 Streamlit 會立即重新執行並顯示輸入框，無須先按送出。
        # 其餘欄位仍保留在表單中，避免輸入其他欄位時反覆刷新。
        reason_options = ["採購入庫", "其他"] if kind == "入庫" else ["設備維修", "定期保養", "其他"]
        reason_choice = st.selectbox("原因", reason_options, key=f"movement_reason_{kind}")
        custom_reason = st.text_input("請填寫原因", key=f"movement_custom_reason_{kind}") if reason_choice == "其他" else ""
        with st.form("movement_form"):
            qty = st.number_input("數量", min_value=0.01, value=1.0, step=1.0)
            person = st.selectbox("領用人 / 相關人員", staff)
            equipment_id = st.text_input("使用設備", value="") if kind == "出庫" else ""
            reference_no = st.text_input("採購單 / 維修單 / 參考單號")
            note = st.text_area("備註")
            submit = st.form_submit_button("確認並登記異動", use_container_width=True)
        if submit:
            try:
                if reason_choice == "其他" and not custom_reason.strip():
                    st.error("原因選擇「其他」時，請填寫具體原因。")
                else:
                    reason = custom_reason.strip() if reason_choice == "其他" else reason_choice
                    add_movement(kind, item["id"], qty, person, reason, equipment_id.strip(), reference_no.strip(), note.strip())
                    st.success(f"{kind}完成。系統已記錄時間、人員、數量及異動前後庫存。")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    elif page == "庫存查詢":
        st.title("庫存查詢")
        df = stock_df()
        if df.empty:
            st.info("尚無備品資料。")
            return
        q = st.text_input("搜尋備品編號、名稱、規格、儲位或設備編號")
        if q:
            mask = df.astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)
            df = df[mask]
        st.dataframe(df.drop(columns=["id"]), use_container_width=True, hide_index=True)
        st.download_button("下載目前庫存 CSV", df.drop(columns=["id"]).to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                           file_name=f"目前庫存_{date.today():%Y%m%d}.csv", mime="text/csv")

    elif page == "缺少清單":
        st.title("缺少清單")
        df = stock_df()
        if df.empty:
            st.info("尚無備品資料。")
            return
        shortage = df[df["目前庫存"] < df["最低庫存"]].copy()
        shortage["缺少數量"] = (shortage["最低庫存"] - shortage["目前庫存"]).clip(lower=0)
        shortage["建議補貨量"] = (shortage["目標庫存"] - shortage["目前庫存"]).clip(lower=0)
        shortage["優先級"] = shortage["目前庫存"].apply(lambda x: "缺料" if x <= 0 else "低庫存")
        st.caption("缺少清單以目前庫存低於最低庫存為判斷條件；建議補貨量補至目標庫存。")
        if shortage.empty:
            st.success("目前沒有低於最低庫存的備品。")
        else:
            st.dataframe(shortage[["優先級","備品編號","備品名稱","規格","儲位","關聯設備編號","目前庫存","最低庫存","目標庫存","缺少數量","建議補貨量","單位"]].sort_values(["目前庫存","備品編號"]), use_container_width=True, hide_index=True)
        export = shortage.drop(columns=["id"], errors="ignore")
        st.download_button("下載缺少清單 Excel", excel_bytes({"缺少清單":export}), file_name=f"缺少清單_{date.today():%Y%m%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    elif page == "月報與匯出":
        st.title("月報與匯出")
        today = date.today()
        month = st.date_input("選擇報表月份（請選該月份任一天）", value=today)
        start = date(month.year, month.month, 1)
        end = date(month.year + (month.month == 12), 1 if month.month == 12 else month.month + 1, 1)
        df = stock_df()
        if df.empty:
            st.info("尚無備品資料。")
            return
        with connect() as con:
            movements = query_df("""
                SELECT m.created_at AS 時間,m.movement_type AS 異動類型,i.code AS 備品編號,
                       i.name AS 備品名稱,i.specification AS 規格,i.unit AS 單位,m.qty AS 數量,
                       m.staff_name AS 相關人員,m.operator_username AS 操作帳號,m.reason AS 原因,
                       m.equipment_id AS 設備編號,m.reference_no AS 參考單號,m.note AS 備註,
                       m.before_qty AS 異動前庫存,m.after_qty AS 異動後庫存
                FROM movements m JOIN items i ON i.id=m.item_id
                WHERE m.created_at >= %s AND m.created_at < %s ORDER BY m.created_at,m.id
            """, con, params=(start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 00:00:00")))
        with connect() as con:
            summary = query_df("""
                SELECT i.id,i.code AS 備品編號,i.name AS 備品名稱,i.specification AS 規格,i.unit AS 單位,
                  i.opening_qty AS 期初建檔數量,
                  COALESCE(SUM(CASE WHEN m.created_at < %s AND m.movement_type IN ('入庫','盤點增加') THEN m.qty
                                    WHEN m.created_at < %s AND m.movement_type IN ('出庫','盤點減少') THEN -m.qty ELSE 0 END),0)
                  + i.opening_qty AS 月初庫存,
                  COALESCE(SUM(CASE WHEN m.created_at >= %s AND m.created_at < %s AND m.movement_type='入庫' THEN m.qty
                                    WHEN m.created_at >= %s AND m.created_at < %s AND m.movement_type='盤點增加' THEN m.qty ELSE 0 END),0) AS 當月入庫,
                  COALESCE(SUM(CASE WHEN m.created_at >= %s AND m.created_at < %s AND m.movement_type='出庫' THEN m.qty
                                    WHEN m.created_at >= %s AND m.created_at < %s AND m.movement_type='盤點減少' THEN m.qty ELSE 0 END),0) AS 當月出庫
                FROM items i LEFT JOIN movements m ON m.item_id=i.id
                WHERE i.active=1 GROUP BY i.id ORDER BY i.code
            """, con, params=(start.strftime("%Y-%m-%d 00:00:00"),start.strftime("%Y-%m-%d 00:00:00"),
                              start.strftime("%Y-%m-%d 00:00:00"),end.strftime("%Y-%m-%d 00:00:00"),
                              start.strftime("%Y-%m-%d 00:00:00"),end.strftime("%Y-%m-%d 00:00:00"),
                              start.strftime("%Y-%m-%d 00:00:00"),end.strftime("%Y-%m-%d 00:00:00"),
                              start.strftime("%Y-%m-%d 00:00:00"),end.strftime("%Y-%m-%d 00:00:00")))
        summary["月末庫存"] = summary["月初庫存"] + summary["當月入庫"] - summary["當月出庫"]
        summary = summary.merge(df[["備品編號","最低庫存","目標庫存","單位成本"]], on="備品編號", how="left")
        summary["月末庫存金額"] = summary["月末庫存"] * summary["單位成本"]
        st.subheader(f"{month.year} 年 {month.month} 月庫存摘要")
        a,b,c = st.columns(3)
        a.metric("當月入庫總量", f"{summary['當月入庫'].sum():,.2f}")
        b.metric("當月出庫總量", f"{summary['當月出庫'].sum():,.2f}")
        c.metric("月末庫存金額", f"{summary['月末庫存金額'].sum():,.2f}")
        st.dataframe(summary.drop(columns=["id"]), use_container_width=True, hide_index=True)
        st.subheader("當月異動明細")
        st.dataframe(movements, use_container_width=True, hide_index=True)
        st.download_button("下載 Excel 月報（摘要＋異動明細＋缺少清單）",
            excel_bytes({"月庫存摘要":summary.drop(columns=["id"]), "異動明細":movements,
                         "缺少清單":make_shortage_df(df)}),
            file_name=f"備品月報_{month.year}{month.month:02d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    elif page == "異動紀錄":
        st.title("異動紀錄")
        require_admin()
        with connect() as con:
            df = query_df("""SELECT m.id AS 紀錄編號,m.created_at AS 時間,m.movement_type AS 類型,
                i.code AS 備品編號,i.name AS 備品名稱,m.qty AS 數量,m.before_qty AS 異動前庫存,
                m.after_qty AS 異動後庫存,m.staff_name AS "領用/相關人員",m.operator_username AS 操作帳號,
                m.reason AS 原因,m.equipment_id AS 設備編號,m.reference_no AS 參考單號,m.note AS 備註
                FROM movements m JOIN items i ON i.id=m.item_id ORDER BY m.id DESC LIMIT 5000""", con)
        q = st.text_input("搜尋紀錄（備品編號、名稱、人員、原因、設備編號）")
        if q:
            df = df[df.astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)]
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("匯出異動紀錄 Excel", excel_bytes({"異動紀錄":df}), "異動紀錄.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    elif page == "備品資料管理":
        st.title("備品資料管理")
        require_admin()
        st.download_button("下載 Excel 匯入範本", template_xlsx(), "備品清單匯入範本.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("#### 匯入現有 Excel")
        st.caption("必要欄位：備品編號、備品名稱。若匯入既有編號，會更新基本資料；只有新增編號才會採用期初庫存。請先備份資料庫。")
        uploaded = st.file_uploader("選擇 .xlsx 或 .csv 檔案", type=["xlsx","csv"], key="item_import")
        if uploaded:
            try:
                raw = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
                imported = normalize_import_columns(raw)
                st.write("資料預覽")
                st.dataframe(imported.head(20), use_container_width=True, hide_index=True)
                if st.button("確認匯入 / 更新備品資料"):
                    required = {"code","name"}
                    if not required.issubset(imported.columns):
                        st.error("找不到必要欄位。請使用範本或將欄位命名為「備品編號、備品名稱」。")
                    else:
                        imported = imported.fillna("")
                        added = updated = 0
                        with connect() as con:
                            for _, r in imported.iterrows():
                                code = str(r.get("code","")).strip()
                                name = str(r.get("name","")).strip()
                                if not code or not name:
                                    continue
                                def txt(k, default=""):
                                    val = r.get(k, default)
                                    return str(val).strip() if val is not None else default
                                def num(k, default=0):
                                    val = r.get(k, default)
                                    try: return float(val) if str(val).strip() != "" else float(default)
                                    except: return float(default)
                                old = con.execute("SELECT id FROM items WHERE code=%s", (code,)).fetchone()
                                vals = (name,txt("specification"),txt("category"),txt("unit","個") or "個",
                                        txt("location"),txt("equipment_id"),max(0,num("min_stock")),
                                        max(0,num("target_stock")),max(0,num("unit_cost")))
                                if old:
                                    con.execute("""UPDATE items SET name=%s,specification=%s,category=%s,unit=%s,location=%s,
                                        equipment_id=%s,min_stock=%s,target_stock=%s,unit_cost=%s,updated_at=%s WHERE code=%s""",
                                        vals+(now_str(),code))
                                    updated += 1
                                else:
                                    opening = max(0,num("opening_qty"))
                                    con.execute("""INSERT INTO items(code,name,specification,category,unit,location,equipment_id,
                                        min_stock,target_stock,unit_cost,opening_qty,active,created_at,updated_at)
                                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                        (code,)+vals+(opening,1,now_str(),now_str()))
                                    added += 1
                            con.commit()
                        log_action(user["username"], "匯入備品", f"新增 {added} 筆；更新 {updated} 筆")
                        st.success(f"匯入完成：新增 {added} 筆，更新 {updated} 筆。")
                        st.rerun()
            except Exception as e:
                st.error(f"檔案讀取失敗：{e}")
        st.markdown("#### 新增單筆備品")
        with st.form("add_item_form"):
            c1,c2,c3 = st.columns(3)
            code = c1.text_input("備品編號 *")
            name = c2.text_input("備品名稱 *")
            spec = c3.text_input("規格")
            c4,c5,c6 = st.columns(3)
            category = c4.text_input("類別")
            unit = c5.text_input("單位", value="個")
            location = c6.text_input("儲位")
            c7,c8,c9 = st.columns(3)
            equipment = c7.text_input("關聯設備編號")
            min_stock = c8.number_input("最低庫存", min_value=0.0, step=1.0)
            target_stock = c9.number_input("目標庫存", min_value=0.0, step=1.0)
            c10,c11 = st.columns(2)
            cost = c10.number_input("單位成本", min_value=0.0, step=1.0)
            opening = c11.number_input("期初庫存", min_value=0.0, step=1.0)
            save = st.form_submit_button("新增備品")
        if save:
            if not code.strip() or not name.strip():
                st.error("備品編號與名稱為必填。")
            else:
                try:
                    with connect() as con:
                        con.execute("""INSERT INTO items(code,name,specification,category,unit,location,equipment_id,
                            min_stock,target_stock,unit_cost,opening_qty,active,created_at,updated_at)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (code.strip(),name.strip(),spec.strip(),category.strip(),unit.strip() or "個",location.strip(),
                             equipment.strip(),min_stock,target_stock,cost,opening,1,now_str(),now_str()))
                        con.commit()
                    log_action(user["username"], "新增備品", code.strip())
                    st.success("新增成功。")
                    st.rerun()
                except psycopg.IntegrityError:
                    st.error("備品編號已存在。")
        st.markdown("#### 停用備品")
        df = stock_df()
        if not df.empty:
            item_row = st.selectbox("選擇要停用的備品", df.apply(lambda r:f"{r['備品編號']} | {r['備品名稱']}",axis=1).tolist())
            if st.button("停用選取備品"):
                code_to_disable = item_row.split(" | ",1)[0]
                with connect() as con:
                    con.execute("UPDATE items SET active=0,updated_at=%s WHERE code=%s", (now_str(),code_to_disable))
                    con.commit()
                log_action(user["username"], "停用備品", code_to_disable)
                st.success("已停用；歷史異動紀錄保留。")
                st.rerun()

    elif page == "人員管理":
        st.title("人員管理")
        require_admin()
        with st.form("staff_add"):
            name = st.text_input("同仁姓名")
            dept = st.text_input("部門", value="技術機械部")
            save = st.form_submit_button("新增 / 啟用人員")
        if save:
            if not name.strip():
                st.error("姓名不可空白。")
            else:
                with connect() as con:
                    con.execute("INSERT INTO staff(name,department,active) VALUES(%s,%s,1) ON CONFLICT(name) DO UPDATE SET department=excluded.department,active=1",
                                (name.strip(),dept.strip()))
                    con.commit()
                log_action(user["username"], "新增/啟用人員", name.strip())
                st.success("人員已新增或重新啟用。")
                st.rerun()
        with connect() as con:
            staffdf = query_df("SELECT name AS 姓名,department AS 部門,CASE active WHEN 1 THEN '啟用' ELSE '停用' END AS 狀態 FROM staff ORDER BY name",con)
        st.dataframe(staffdf, use_container_width=True, hide_index=True)
        active_names = staffdf[staffdf["狀態"]=="啟用"]["姓名"].tolist()
        if active_names:
            selected_staff = st.selectbox("選擇停用人員", active_names)
            if st.button("停用此人員"):
                with connect() as con:
                    con.execute("UPDATE staff SET active=0 WHERE name=%s", (selected_staff,))
                    con.commit()
                log_action(user["username"], "停用人員", selected_staff)
                st.rerun()

    elif page == "帳號與權限":
        st.title("帳號與權限")
        change_own_password()
        if user["role"] == "admin":
            st.divider()
            st.subheader("建立 / 更新登入帳號")
            with st.form("user_create"):
                username = st.text_input("登入帳號（英文或工號）")
                display = st.text_input("顯示名稱")
                password = st.text_input("初始密碼（至少 10 個字元）", type="password")
                role = st.selectbox("權限", ["operator","admin"], format_func=lambda x:"一般操作人員" if x=="operator" else "管理員")
                active = st.checkbox("啟用帳號", value=True)
                save = st.form_submit_button("建立帳號")
            if save:
                if not username.strip() or not display.strip() or len(password)<10:
                    st.error("帳號、顯示名稱不可空白，密碼至少 10 個字元。")
                else:
                    salt,digest = hash_password(password)
                    try:
                        with connect() as con:
                            con.execute("""INSERT INTO users(username,display_name,salt,password_hash,role,active,created_at)
                                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                                (username.strip(),display.strip(),salt,digest,role,1 if active else 0,now_str()))
                            con.commit()
                        log_action(user["username"], "建立帳號", f"{username.strip()} / {role}")
                        st.success("帳號建立成功。")
                        st.rerun()
                    except psycopg.IntegrityError:
                        st.error("登入帳號已存在。第一版請勿重複建立；若需重設密碼，請由管理員依公司流程處理。")
            with connect() as con:
                usersdf = query_df("SELECT username AS 帳號,display_name AS 顯示名稱,role AS 權限,active AS 啟用,created_at AS 建立時間 FROM users ORDER BY username",con)
            st.dataframe(usersdf, use_container_width=True, hide_index=True)
            st.caption("管理員可建立帳號。帳號停用/密碼重設等功能可在後續版本擴充；請勿共用管理員帳號。")
        else:
            st.info("一般操作人員可以修改自己的密碼。帳號管理僅限管理員。")

    elif page == "備份與還原":
        st.title("備份與還原")
        require_admin()
        st.warning(
            "雲端備份會下載五張資料表的 JSON 檔，請存放在公司核准且有存取權限的位置。"
            "備份檔包含帳號密碼雜湊及完整庫存紀錄，請勿公開分享。還原會覆蓋雲端資料，"
            "執行前務必先下載目前備份。"
        )
        table_names = ["users", "staff", "items", "movements", "audit_log"]
        if st.button("準備雲端資料庫備份", use_container_width=True):
            try:
                snapshot = {"format": "department_spares_postgresql_v1", "created_at": now_str(), "tables": {}}
                with connect() as con:
                    for table in table_names:
                        with con.cursor() as cur:
                            cur.execute(f'SELECT * FROM "{table}" ORDER BY id')
                            snapshot["tables"][table] = [dict(row) for row in cur.fetchall()]
                payload = json.dumps(snapshot, ensure_ascii=False, indent=2, default=str).encode("utf-8")
                st.download_button(
                    "下載雲端備份 JSON", data=payload,
                    file_name=f"spares_postgres_backup_{datetime.now():%Y%m%d_%H%M%S}.json",
                    mime="application/json", use_container_width=True,
                )
                log_action(user["username"], "準備雲端備份", f"包含 {len(table_names)} 張資料表")
            except Exception as e:
                st.error(f"備份準備失敗：{e}")

        st.divider()
        st.subheader("還原雲端 JSON 備份")
        st.caption("只接受本系統產生的 JSON 備份。還原會取代五張資料表全部資料，請先下載目前備份。")
        uploaded = st.file_uploader("選擇雲端備份 JSON", type=["json"], key="restore_pg_json")
        confirm_restore = st.checkbox("我已了解還原會覆蓋雲端五張資料表", key="confirm_pg_restore")
        if uploaded and confirm_restore and st.button("確認還原雲端資料", type="primary"):
            try:
                snapshot = json.loads(uploaded.getvalue().decode("utf-8"))
                if snapshot.get("format") != "department_spares_postgresql_v1":
                    raise ValueError("備份格式不符，未還原。")
                data = snapshot.get("tables", {})
                if set(data) != set(table_names):
                    raise ValueError("備份資料表清單不完整，未還原。")
                with connect() as con:
                    with con.cursor() as cur:
                        for table in table_names:
                            if not isinstance(data[table], list):
                                raise ValueError(f"{table} 資料格式不正確。")
                        for table in ["audit_log", "movements", "items", "staff", "users"]:
                            cur.execute(f'DELETE FROM "{table}"')
                        for table in ["users", "staff", "items", "movements", "audit_log"]:
                            rows = data[table]
                            if not rows:
                                continue
                            cur.execute("""
                                SELECT column_name FROM information_schema.columns
                                WHERE table_schema='spares' AND table_name=%s
                                ORDER BY ordinal_position
                            """, (table,))
                            cols = [r["column_name"] for r in cur.fetchall()]
                            for row in rows:
                                if not isinstance(row, dict) or set(row) != set(cols):
                                    raise ValueError(f"{table} 備份欄位不符合目前資料表。")
                            col_sql = ", ".join('"' + c.replace('"', '""') + '"' for c in cols)
                            placeholders = ", ".join(["%s"] * len(cols))
                            cur.executemany(
                                f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})',
                                [tuple(row[c] for c in cols) for row in rows],
                            )
                        for table in table_names:
                            cur.execute(
                                f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                                f"GREATEST(COALESCE((SELECT MAX(id) FROM spares.{table}), 1), 1), "
                                f"EXISTS(SELECT 1 FROM spares.{table}))",
                                (f"spares.{table}",),
                            )
                log_action(user["username"], "還原雲端備份", uploaded.name)
                st.success("雲端資料還原完成。請重新檢查庫存及異動紀錄。")
                st.rerun()
            except Exception as e:
                st.error(f"還原失敗，交易已取消：{e}")

    else:
        st.title(page)

def excel_bytes(sheets):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe = name[:31]
            (df if isinstance(df,pd.DataFrame) else pd.DataFrame(df)).to_excel(writer, index=False, sheet_name=safe)
    return buf.getvalue()

def make_shortage_df(df):
    if df.empty:
        return df.copy()
    s = df[df["目前庫存"] < df["最低庫存"]].copy()
    s["缺少數量"] = (s["最低庫存"] - s["目前庫存"]).clip(lower=0)
    s["建議補貨量"] = (s["目標庫存"] - s["目前庫存"]).clip(lower=0)
    s["優先級"] = s["目前庫存"].apply(lambda x: "缺料" if x <= 0 else "低庫存")
    return s.drop(columns=["id"], errors="ignore")

init_db()
if "user" not in st.session_state:
    login_screen()
else:
    main_app()
