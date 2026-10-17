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
from zoneinfo import ZoneInfo
from pathlib import Path
from streamlit_autorefresh import st_autorefresh

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
OUTPUT_DIR = APP_DIR / "output"
BACKUP_DIR = Path(os.environ.get("SPARES_BACKUP_DIR", str(APP_DIR / "backups"))).expanduser()
for folder in (OUTPUT_DIR, BACKUP_DIR):
    folder.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="部門管理系統 V2.3 / Hệ thống quản lý bộ phận V2.3", page_icon="📦", layout="wide")


# ===== 中越雙語介面（V1.3）=====
UI_TEXT = {
    "中文": {
        "部門備品管理系統": "部門備品管理系統",
        "語言 / Ngôn ngữ": "語言 / Ngôn ngữ",
        "中文 / Tiếng Trung": "中文 / Tiếng Trung",
        "越南語 / Tiếng Việt": "越南語 / Tiếng Việt",
        "登入帳號": "登入帳號", "密碼": "密碼", "登入": "登入",
        "建立員工帳號": "建立員工帳號", "修改我的密碼": "修改我的密碼",
        "功能選單": "功能選單", "總覽儀表板": "總覽儀表板",
        "入庫/出庫": "入庫/出庫", "庫存查詢": "庫存查詢",
        "缺貨清單": "缺貨清單", "月報與匯出": "月報與匯出",
        "異動紀錄": "異動紀錄", "備品資料管理": "備品資料管理",
        "人員與權限": "人員與權限", "備份與還原": "備份與還原",
        "登出": "登出", "系統管理員": "系統管理員", "管理員權限": "管理員權限",
        "員工權限": "員工權限", "搜尋記錄（備品編號、姓名、人員、原因、設備編號）": "搜尋記錄（備品編號、姓名、人員、原因、設備編號）",
        "匯出異動紀錄Excel": "匯出異動紀錄Excel",
        "備品編號": "備品編號", "備品名稱": "備品名稱", "規格": "規格",
        "類別": "類別", "單位": "單位", "儲位": "儲位", "關聯設備編號": "關聯設備編號",
        "最低庫存": "最低庫存", "目標庫存": "目標庫存", "單位成本": "單位成本",
        "目前庫存": "目前庫存", "紀錄編號": "紀錄編號", "時間": "時間",
        "類型": "類型", "數量": "數量", "異動前庫存": "異動前庫存",
        "異動後庫存": "異動後庫存", "領用/相關人員": "領用/相關人員",
        "操作帳號": "操作帳號", "原因": "原因", "設備編號": "設備編號",
        "參考單號": "參考單號", "備註": "備註", "入庫": "入庫", "出庫": "出庫",
        "盤點增加": "盤點增加", "盤點減少": "盤點減少",
        "帳號或密碼錯誤，或帳號已停用。": "帳號或密碼錯誤，或帳號已停用。",
        "此功能僅限系統管理員使用。": "此功能僅限系統管理員使用。",
        "此功能需要管理員權限或系統管理員權限。": "此功能需要管理員權限或系統管理員權限。",
    },
    "越南語": {
        "部門備品管理系統": "Hệ thống quản lý vật tư bộ phận",
        "語言 / Ngôn ngữ": "Ngôn ngữ / 語言",
        "中文 / Tiếng Trung": "Tiếng Trung / 中文",
        "越南語 / Tiếng Việt": "Tiếng Việt / 越南語",
        "登入帳號": "Tên tài khoản", "密碼": "Mật khẩu", "登入": "Đăng nhập",
        "建立員工帳號": "Tạo tài khoản nhân viên", "修改我的密碼": "Đổi mật khẩu",
        "功能選單": "Danh mục chức năng", "總覽儀表板": "Bảng điều khiển tổng quan",
        "入庫/出庫": "Nhập kho / Xuất kho", "庫存查詢": "Tra cứu tồn kho",
        "缺貨清單": "Danh sách thiếu hàng", "月報與匯出": "Báo cáo tháng và xuất dữ liệu",
        "異動紀錄": "Lịch sử giao dịch", "備品資料管理": "Quản lý dữ liệu vật tư",
        "人員與權限": "Nhân sự và phân quyền", "備份與還原": "Sao lưu và khôi phục",
        "登出": "Đăng xuất", "系統管理員": "Quản trị viên hệ thống", "管理員權限": "Quyền quản lý",
        "員工權限": "Quyền nhân viên", "搜尋記錄（備品編號、姓名、人員、原因、設備編號）": "Tìm kiếm lịch sử (mã vật tư, tên, người dùng, lý do, mã thiết bị)",
        "匯出異動紀錄Excel": "Xuất lịch sử giao dịch Excel",
        "備品編號": "Mã vật tư", "備品名稱": "Tên vật tư", "規格": "Quy cách",
        "類別": "Danh mục", "單位": "Đơn vị", "儲位": "Vị trí lưu kho", "關聯設備編號": "Mã thiết bị liên quan",
        "最低庫存": "Tồn kho tối thiểu", "目標庫存": "Tồn kho mục tiêu", "單位成本": "Đơn giá",
        "目前庫存": "Tồn kho hiện tại", "紀錄編號": "Mã giao dịch", "時間": "Thời gian",
        "類型": "Loại giao dịch", "數量": "Số lượng", "異動前庫存": "Tồn kho trước giao dịch",
        "異動後庫存": "Tồn kho sau giao dịch", "領用/相關人員": "Người nhận / người liên quan",
        "操作帳號": "Tài khoản thao tác", "原因": "Lý do", "設備編號": "Mã thiết bị",
        "參考單號": "Mã tham chiếu", "備註": "Ghi chú", "入庫": "Nhập kho", "出庫": "Xuất kho",
        "盤點增加": "Tăng sau kiểm kê", "盤點減少": "Giảm sau kiểm kê",
        "帳號或密碼錯誤，或帳號已停用。": "Tên tài khoản hoặc mật khẩu không đúng, hoặc tài khoản đã bị vô hiệu hóa.",
        "此功能僅限系統管理員使用。": "Chức năng này chỉ dành cho quản trị viên hệ thống.",
        "此功能需要管理員權限或系統管理員權限。": "Chức năng này yêu cầu quyền quản lý hoặc quản trị viên hệ thống.",
        "第一版｜共用庫存、異動追蹤、低庫存預警": "Phiên bản nội bộ | Tồn kho dùng chung, theo dõi giao dịch, cảnh báo tồn kho thấp",
        "登入成功": "Đăng nhập thành công",
        "請輸入": "Vui lòng nhập",
        "新增": "Thêm mới", "儲存": "Lưu", "更新": "Cập nhật", "刪除": "Xóa",
        "取消": "Hủy", "確認": "Xác nhận", "匯出": "Xuất dữ liệu",
        "目前沒有資料。": "Hiện chưa có dữ liệu.",
        "目前沒有缺料項目。": "Hiện không có vật tư thiếu hàng.",
        "備品資料": "Dữ liệu vật tư", "庫存": "Tồn kho",
        "月報": "Báo cáo tháng", "開始日期": "Ngày bắt đầu", "結束日期": "Ngày kết thúc",
        "選擇備品": "Chọn vật tư", "選擇人員": "Chọn nhân viên",
        "領用人員": "Người nhận vật tư", "維修原因": "Lý do sửa chữa",
        "設備維修": "Bảo trì thiết bị", "採購入庫": "Nhập kho mua hàng",
        "員工帳號": "Tài khoản nhân viên", "顯示名稱": "Tên hiển thị",
        "角色": "Vai trò", "啟用": "Kích hoạt", "停用": "Vô hiệu hóa",
        "舊密碼": "Mật khẩu cũ", "新密碼": "Mật khẩu mới", "確認新密碼": "Xác nhận mật khẩu mới",
        "備份資料庫": "Sao lưu cơ sở dữ liệu", "還原資料庫": "Khôi phục cơ sở dữ liệu",
        "選擇檔案": "Chọn tệp", "下載": "Tải xuống",
        "入庫數量": "Số lượng nhập kho", "出庫數量": "Số lượng xuất kho",
        "最低庫存量": "Mức tồn kho tối thiểu", "目標庫存量": "Mức tồn kho mục tiêu",
        "請選擇": "Vui lòng chọn", "成功": "Thành công", "失敗": "Thất bại",
        '人員技能矩陣': 'Ma trận kỹ năng nhân sự',
        '考試紀錄': 'Lịch sử thi / kiểm tra',
        '培訓紀錄': 'Lịch sử đào tạo',
        '刪除人員（管理權限）': 'Xóa nhân sự (quyền quản lý)',
        '選擇要刪除的人員': 'Chọn nhân sự cần xóa',
        '我確認刪除此人員及其技能、培訓、考試資料；此操作無法復原': 'Tôi xác nhận xóa nhân sự cùng dữ liệu kỹ năng, đào tạo và thi; thao tác không thể hoàn tác',
        '永久刪除人員': 'Xóa nhân sự vĩnh viễn',
        '員工編號': 'Mã nhân viên',
        '考試日期': 'Ngày thi',
        '考試名稱／項目': 'Tên / hạng mục thi',
        '相關技能': 'Kỹ năng liên quan',
        '考試分數': 'Điểm thi',
        '滿分': 'Điểm tối đa',
        '考試結果': 'Kết quả thi',
        '考官／評核人員': 'Giám khảo / người đánh giá',
        '新增考試紀錄': 'Thêm lịch sử thi',
        '技能項目': 'Kỹ năng',
        '評估日期': 'Ngày đánh giá',
        '評估人員': 'Người đánh giá',
        '儲存技能等級': 'Lưu cấp độ kỹ năng',
        '開始處理時間（YYYY-MM-DD HH:MM:SS）': 'Thời gian bắt đầu xử lý (YYYY-MM-DD HH:MM:SS)',
        '處理完成時間（未完成可留空）': 'Thời gian hoàn tất xử lý (có thể để trống nếu chưa hoàn tất)',
        '處理人員': 'Người xử lý',
        '處理時數': 'Thời gian xử lý (giờ)',
        '人員處理異常時間分析': 'Phân tích thời gian xử lý sự cố theo nhân sự',
        '處理異常件數': 'Số sự cố đã xử lý',
        '平均處理時數': 'Thời gian xử lý trung bình (giờ)',
        '累計處理時數': 'Tổng thời gian xử lý (giờ)',
        '最長處理時數': 'Thời gian xử lý dài nhất (giờ)',
        '異常嚴重程度': 'Mức độ nghiêm trọng',
        '異常原因／根本原因': 'Nguyên nhân sự cố / nguyên nhân gốc rễ',
        '處理措施與結果': 'Biện pháp và kết quả xử lý',
        '異常現象': 'Hiện tượng bất thường',
        '異常原因': 'Nguyên nhân sự cố',
        '處理完成時間': 'Thời gian hoàn tất xử lý',
        '開始處理時間': 'Thời gian bắt đầu xử lý',
        '管理權限': 'Quyền quản lý',
        '模塊首頁': 'Trang chủ mô-đun',
        '三大功能模塊': 'Ba mô-đun chức năng chính',
        '人員管理模塊': 'Mô-đun quản lý nhân sự',
        '設備管理模塊': 'Mô-đun quản lý thiết bị',
        '備品管理模塊': 'Mô-đun quản lý vật tư',
        '人員總覽': 'Tổng quan nhân sự',
        '人員資料與技能': 'Hồ sơ nhân sự và kỹ năng',
        '技能項目管理': 'Quản lý danh mục kỹ năng',
        '培訓紀錄': 'Lịch sử đào tạo',
        '設備總覽': 'Tổng quan thiết bị',
        '設備資料管理': 'Quản lý dữ liệu thiết bị',
        '保養計畫與紀錄': 'Kế hoạch và lịch sử bảo trì',
        '設備異常紀錄': 'Lịch sử bất thường thiết bị',
        '員工編號': 'Mã nhân viên',
        '姓名': 'Họ và tên',
        '職位': 'Chức vụ',
        '到職日期': 'Ngày vào làm',
        '技能': 'Kỹ năng',
        '技能等級': 'Cấp độ kỹ năng',
        '綜合技能等級': 'Cấp độ kỹ năng tổng hợp',
        '初級 (1-2)': 'Sơ cấp (1-2)',
        '中級 (3-5)': 'Trung cấp (3-5)',
        '熟練 (6-8)': 'Thành thạo (6-8)',
        '專家 (9-10)': 'Chuyên gia (9-10)',
        '證照': 'Chứng chỉ',
        '培訓紀錄/訓練內容': 'Lịch sử đào tạo / nội dung đào tạo',
        '聯絡電話': 'Số điện thoại liên hệ',
        '在職狀態': 'Trạng thái làm việc',
        '備註': 'Ghi chú',
        '新增人員資料': 'Thêm hồ sơ nhân sự',
        '新增人員': 'Thêm nhân sự',
        '更新人員資料': 'Cập nhật hồ sơ nhân sự',
        '技能名稱': 'Tên kỹ năng',
        '技能類別': 'Loại kỹ năng',
        '技能說明': 'Mô tả kỹ năng',
        '新增技能項目': 'Thêm kỹ năng',
        '技能清單': 'Danh sách kỹ năng',
        '培訓日期': 'Ngày đào tạo',
        '培訓主題': 'Chủ đề đào tạo',
        '培訓時數': 'Số giờ đào tạo',
        '培訓結果': 'Kết quả đào tạo',
        '新增培訓紀錄': 'Thêm lịch sử đào tạo',
        '設備編號': 'Mã thiết bị',
        '設備名稱': 'Tên thiết bị',
        '型號': 'Model',
        '位置': 'Vị trí',
        '負責部門': 'Bộ phận phụ trách',
        '設備負責人': 'Người phụ trách thiết bị',
        '安裝日期': 'Ngày lắp đặt',
        '設備狀態': 'Trạng thái thiết bị',
        '保養週期（天）': 'Chu kỳ bảo trì (ngày)',
        '上次保養日期': 'Ngày bảo trì gần nhất',
        '下次保養日期': 'Ngày bảo trì tiếp theo',
        '新增設備': 'Thêm thiết bị',
        '設備清單': 'Danh sách thiết bị',
        '設備數量': 'Số lượng thiết bị',
        '正常設備': 'Thiết bị bình thường',
        '待保養設備': 'Thiết bị đến hạn bảo trì',
        '未結案異常': 'Sự cố chưa đóng',
        '保養日期': 'Ngày bảo trì',
        '保養類型': 'Loại bảo trì',
        '維修技術員': 'Kỹ thuật viên',
        '維修時數': 'Số giờ bảo trì',
        '保養結果': 'Kết quả bảo trì',
        '使用備品': 'Vật tư đã sử dụng',
        '下次保養日期（可留空自動計算）': 'Ngày bảo trì tiếp theo (để trống để tự tính)',
        '新增保養紀錄': 'Thêm lịch sử bảo trì',
        '異常發生時間': 'Thời gian xảy ra bất thường',
        '異常等級': 'Mức độ sự cố',
        '異常現象': 'Hiện tượng bất thường',
        '根本原因': 'Nguyên nhân gốc rễ',
        '處理措施': 'Biện pháp xử lý',
        '停機時數': 'Số giờ dừng máy',
        '處理狀態': 'Trạng thái xử lý',
        '通報人員': 'Người báo cáo',
        '新增異常紀錄': 'Thêm bản ghi sự cố',
        '異常紀錄清單': 'Danh sách sự cố',
        '一般': 'Thông thường',
        '重大': 'Nghiêm trọng',
        '緊急': 'Khẩn cấp',
        '未結案': 'Chưa đóng',
        '處理中': 'Đang xử lý',
        '已結案': 'Đã đóng',
        '正常': 'Bình thường',
        '維修中': 'Đang sửa chữa',
        '停用': 'Ngừng hoạt động',
        '在職': 'Đang làm việc',
        '離職': 'Đã nghỉ việc',
        '待評估': 'Chưa đánh giá',
        '初級': 'Cơ bản',
        '中級': 'Trung cấp',
        '熟練': 'Thành thạo',
        '專家': 'Chuyên gia',
        '人員管理': 'Quản lý nhân sự',
        '設備管理': 'Quản lý thiết bị',
        '備品管理': 'Quản lý vật tư',
        '目前沒有資料。': 'Hiện chưa có dữ liệu.',
        '請先建立設備資料。': 'Vui lòng tạo dữ liệu thiết bị trước.',
        '請先建立人員資料。': 'Vui lòng tạo hồ sơ nhân sự trước.',
        '資料已儲存。': 'Đã lưu dữ liệu.',
        '新增成功。': 'Thêm mới thành công.',
        '已記錄操作。': 'Đã ghi nhận thao tác.',
        '只有管理員可新增或修改資料。': 'Chỉ quản lý mới có thể thêm hoặc chỉnh sửa dữ liệu.',
        '目前沒有待保養設備。': 'Hiện không có thiết bị đến hạn bảo trì.',
        '設備資料與維修紀錄': 'Dữ liệu thiết bị và lịch sử bảo trì',
        '人員技能分布': 'Phân bố kỹ năng nhân sự',
        '設備維修與異常概況': 'Tổng quan bảo trì và sự cố thiết bị',
        '維修時間': 'Thời gian bảo trì',
        '設備異常': 'Sự cố thiết bị',
        '人員技能': 'Kỹ năng nhân sự',
        '總覽儀表板': 'Bảng điều khiển tổng quan',
        '入庫 / 出庫': 'Nhập kho / Xuất kho',
        '缺少清單': 'Danh sách vật tư thiếu',
        '功能選單': 'Danh mục chức năng',
        '建立新帳號': 'Tạo tài khoản mới',
        '更新帳號': 'Cập nhật tài khoản',
        '操作': 'Thao tác',
        '部門': 'Bộ phận',
        '生技': 'Kỹ thuật sản xuất',
        '品保': 'Đảm bảo chất lượng',
        '製造': 'Sản xuất',
        '原因': 'Lý do',
        '其他': 'Khác',
        '定期保養': 'Bảo trì định kỳ',
        '設備維修': 'Bảo trì thiết bị',
        '採購入庫': 'Nhập kho mua hàng',
        '異動類型': 'Loại giao dịch',
        '備品': 'Vật tư',
        '目前庫存：': 'Tồn kho hiện tại: ',
        '搜尋備品（編號、名稱、規格、儲位或關聯設備）': 'Tìm vật tư (mã, tên, quy cách, vị trí lưu kho hoặc thiết bị liên quan)',
        '搜尋備品編號、名稱、規格、儲位或設備編號': 'Tìm mã vật tư, tên, quy cách, vị trí lưu kho hoặc mã thiết bị',
        '優先處理的缺料項目': 'Vật tư thiếu cần ưu tiên xử lý',
        '最近 10 筆異動': '10 giao dịch gần nhất',
        '有效備品種類': 'Số loại vật tư đang sử dụng',
        '低於最低庫存': 'Dưới mức tồn kho tối thiểu',
        '庫存總金額': 'Tổng giá trị tồn kho',
        '目前庫存總數量': 'Tổng số lượng tồn kho hiện tại',
        '缺少數量': 'Số lượng thiếu',
        '建議補貨量': 'Số lượng đề xuất bổ sung',
        '月庫存摘要': 'Tóm tắt tồn kho tháng',
        '當月入庫總量': 'Tổng lượng nhập trong tháng',
        '當月出庫總量': 'Tổng lượng xuất trong tháng',
        '月末庫存金額': 'Giá trị tồn kho cuối tháng',
        '當月異動明細': 'Chi tiết giao dịch trong tháng',
        '下載目前庫存 CSV': 'Tải xuống tồn kho hiện tại (CSV)',
        '下載缺少清單 Excel': 'Tải danh sách vật tư thiếu (Excel)',
        '下載 Excel 月報（摘要＋異動明細＋缺少清單）': 'Tải báo cáo tháng Excel (tóm tắt + chi tiết giao dịch + danh sách thiếu)',
        '下載 Excel 匯入範本': 'Tải mẫu nhập Excel',
        '匯入現有 Excel': 'Nhập dữ liệu Excel hiện có',
        '必要欄位：備品編號、備品名稱。若匯入既有編號，會更新基本資料；只有新增編號才會採用期初庫存。請先備份資料庫。': 'Các trường bắt buộc: mã vật tư, tên vật tư. Nếu mã đã tồn tại, hệ thống cập nhật thông tin cơ bản; chỉ mã mới áp dụng tồn kho ban đầu. Vui lòng sao lưu cơ sở dữ liệu trước.',
        '選擇報表月份（請選該月份任一天）': 'Chọn tháng báo cáo (chọn bất kỳ ngày nào trong tháng)',
        '新增單筆備品': 'Thêm một vật tư',
        '備品編號 *': 'Mã vật tư *',
        '備品名稱 *': 'Tên vật tư *',
        '最低庫存': 'Tồn kho tối thiểu',
        '目標庫存': 'Tồn kho mục tiêu',
        '期初庫存': 'Tồn kho ban đầu',
        '目前沒有低於最低庫存的備品。': 'Hiện không có vật tư nào thấp hơn mức tồn kho tối thiểu.',
        '請先匯入或建立備品資料。': 'Vui lòng nhập hoặc tạo dữ liệu vật tư trước.',
        '請填寫原因': 'Vui lòng nhập lý do',
        '員工權限只能以本人帳號登記出庫。': 'Tài khoản nhân viên chỉ được ghi nhận xuất kho bằng chính tài khoản của mình.',
        '出庫時必須填寫使用設備編號。': 'Khi xuất kho, bắt buộc nhập mã thiết bị sử dụng.',
        '原因選擇「其他」時，請填寫具體原因。': 'Khi chọn lý do “Khác”, vui lòng nhập lý do cụ thể.',
        '確認並登記異動': 'Xác nhận và ghi nhận giao dịch',
        '完成。系統已記錄時間、人員、數量及異動前後庫存。': 'Hoàn tất. Hệ thống đã ghi lại thời gian, người thực hiện, số lượng và tồn kho trước/sau giao dịch.',
        '新增成功。': 'Thêm mới thành công.',
        '新增備品': 'Thêm vật tư',
        '資料預覽': 'Xem trước dữ liệu',
        '確認匯入 / 更新備品資料': 'Xác nhận nhập / cập nhật dữ liệu vật tư',
        '建立 / 更新登入帳號': 'Tạo / cập nhật tài khoản đăng nhập',
        '登入帳號清單': 'Danh sách tài khoản đăng nhập',
        '刪除登入帳號': 'Xóa tài khoản đăng nhập',
        '選擇要更新的帳號': 'Chọn tài khoản cần cập nhật',
        '確認失效': 'Xác nhận ngừng sử dụng',
        '恢復備品': 'Khôi phục vật tư',
        '確認恢復': 'Xác nhận khôi phục',
        '刪除料號': 'Xóa mã vật tư',
        '確認還原，覆蓋目前資料庫': 'Xác nhận khôi phục và ghi đè cơ sở dữ liệu hiện tại',
        '立即建立資料庫備份': 'Tạo bản sao lưu cơ sở dữ liệu ngay',
        '還原資料庫備份（僅管理員）': 'Khôi phục bản sao lưu cơ sở dữ liệu (chỉ quản trị viên)',
        '輸入備品編號、名稱、規格、儲位或設備編號': 'Nhập mã vật tư, tên, quy cách, vị trí lưu kho hoặc mã thiết bị',
        '工號': 'Mã nhân viên',
        '密碼（至少 10 個字元）': 'Mật khẩu (ít nhất 10 ký tự)',
        '部門': 'Bộ phận',
        '建立帳號': 'Tạo tài khoản',
        '請輸入工號；顯示名稱會自動使用工號，新建帳號立即生效，預設為員工權限。': 'Vui lòng nhập mã nhân viên; tên hiển thị sẽ tự động dùng mã nhân viên. Tài khoản mới có hiệu lực ngay và mặc định có quyền nhân viên.',
        '工號不可空白，密碼至少 10 個字元，並請選擇部門。': 'Mã nhân viên không được để trống, mật khẩu phải có ít nhất 10 ký tự và vui lòng chọn bộ phận.',
        '帳號建立成功，現在即可登入。': 'Tạo tài khoản thành công. Bạn có thể đăng nhập ngay.',
        '此工號已存在，請使用其他工號。': 'Mã nhân viên này đã tồn tại. Vui lòng dùng mã khác.',
        '目前密碼': 'Mật khẩu hiện tại',
        '新密碼（至少 10 個字元）': 'Mật khẩu mới (ít nhất 10 ký tự)',
        '再次輸入新密碼': 'Nhập lại mật khẩu mới',
        '更新密碼': 'Cập nhật mật khẩu',
        '目前密碼不正確。': 'Mật khẩu hiện tại không đúng。',
        '新密碼至少需要 10 個字元。': 'Mật khẩu mới phải có ít nhất 10 ký tự.',
        '兩次輸入的新密碼不一致。': 'Hai lần nhập mật khẩu mới không khớp.',
        '密碼已更新。': 'Đã cập nhật mật khẩu.',
        '第一版｜共用庫存、異動追蹤、低庫存預警': 'Phiên bản nội bộ | Tồn kho dùng chung, theo dõi giao dịch, cảnh báo tồn kho thấp',
        '登入：': 'Đăng nhập: ',
        '權限：': 'Quyền: ',
        '生技': 'Kỹ thuật sản xuất',
        '品保': 'Đảm bảo chất lượng',
        '製造': 'Sản xuất',
        '總覽儀表板': 'Bảng điều khiển tổng quan',
        '目前沒有備品資料。請管理員到「備品資料管理」匯入 Excel。': 'Chưa có dữ liệu vật tư. Vui lòng yêu cầu quản trị viên nhập Excel tại mục “Quản lý dữ liệu vật tư”.',
        '優先處理的缺料項目': 'Vật tư thiếu cần ưu tiên xử lý',
        '最近 10 筆異動': '10 giao dịch gần nhất',
        '入庫 / 出庫': 'Nhập kho / Xuất kho',
        '請先匯入或建立備品資料。': 'Vui lòng nhập hoặc tạo dữ liệu vật tư trước.',
        '異動類型': 'Loại giao dịch',
        '搜尋備品（編號、名稱、規格、儲位或關聯設備）': 'Tìm vật tư (mã, tên, quy cách, vị trí lưu kho hoặc thiết bị liên quan)',
        '沒有符合搜尋條件的備品，請修改搜尋文字。': 'Không có vật tư phù hợp. Vui lòng thay đổi từ khóa tìm kiếm.',
        '備品': 'Vật tư',
        '目前庫存：': 'Tồn kho hiện tại: ',
        '請填寫原因': 'Vui lòng nhập lý do',
        '其他': 'Khác',
        '數量': 'Số lượng',
        '領用人 / 相關人員': 'Người nhận / người liên quan',
        '採購單 / 維修單 / 參考單號': 'Mã đơn mua hàng / phiếu sửa chữa / mã tham chiếu',
        '確認並登記異動': 'Xác nhận và ghi nhận giao dịch',
        '員工權限只能以本人帳號登記出庫。': 'Tài khoản nhân viên chỉ được ghi nhận xuất kho bằng chính tài khoản của mình.',
        '出庫時必須填寫使用設備編號。': 'Khi xuất kho, bắt buộc nhập mã thiết bị sử dụng.',
        '原因選擇「其他」時，請填寫具體原因。': 'Khi chọn lý do “Khác”, vui lòng nhập lý do cụ thể.',
        '完成。系統已記錄時間、人員、數量及異動前後庫存。': ' hoàn tất. Hệ thống đã ghi lại thời gian, người thực hiện, số lượng và tồn kho trước/sau giao dịch.',
        '庫存查詢': 'Tra cứu tồn kho',
        '尚無備品資料。': 'Chưa có dữ liệu vật tư.',
        '搜尋備品編號、名稱、規格、儲位或設備編號': 'Tìm mã vật tư, tên, quy cách, vị trí lưu kho hoặc mã thiết bị',
        '下載目前庫存 CSV': 'Tải xuống tồn kho hiện tại (CSV)',
        '缺少清單': 'Danh sách vật tư thiếu',
        '缺少清單以目前庫存低於最低庫存為判斷條件；建議補貨量補至目標庫存。': 'Danh sách thiếu được xác định khi tồn kho hiện tại thấp hơn mức tối thiểu; số lượng đề xuất bổ sung sẽ đưa tồn kho lên mức mục tiêu.',
        '目前沒有低於最低庫存的備品。': 'Hiện không có vật tư nào thấp hơn mức tồn kho tối thiểu.',
        '下載缺少清單 Excel': 'Tải danh sách vật tư thiếu (Excel)',
        '月報與匯出': 'Báo cáo tháng và xuất dữ liệu',
        '選擇報表月份（請選該月份任一天）': 'Chọn tháng báo cáo (chọn bất kỳ ngày nào trong tháng)',
        '年': ' năm ',
        '月庫存摘要': 'Tóm tắt tồn kho tháng',
        '當月異動明細': 'Chi tiết giao dịch trong tháng',
        '下載 Excel 月報（摘要＋異動明細＋缺少清單）': 'Tải báo cáo tháng Excel (tóm tắt + chi tiết giao dịch + danh sách thiếu)',
        '異動紀錄': 'Lịch sử giao dịch',
        '搜尋紀錄（備品編號、名稱、人員、原因、設備編號）': 'Tìm lịch sử (mã vật tư, tên, nhân viên, lý do, mã thiết bị)',
        '匯出異動紀錄 Excel': 'Xuất lịch sử giao dịch Excel',
        '備品資料管理': 'Quản lý dữ liệu vật tư',
        '下載 Excel 匯入範本': 'Tải mẫu nhập Excel',
        '匯入現有 Excel': 'Nhập dữ liệu Excel hiện có',
        '必要欄位：備品編號、備品名稱。若匯入既有編號，會更新基本資料；只有新增編號才會採用期初庫存。請先備份資料庫。': 'Các trường bắt buộc: mã vật tư, tên vật tư. Nếu mã đã tồn tại, hệ thống cập nhật thông tin cơ bản; chỉ mã mới mới áp dụng tồn kho ban đầu. Vui lòng sao lưu cơ sở dữ liệu trước.',
        '選擇 .xlsx 或 .csv 檔案': 'Chọn tệp .xlsx hoặc .csv',
        '資料預覽': 'Xem trước dữ liệu',
        '確認匯入 / 更新備品資料': 'Xác nhận nhập / cập nhật dữ liệu vật tư',
        '找不到必要欄位。請使用範本或將欄位命名為「備品編號、備品名稱」。': 'Không tìm thấy trường bắt buộc. Vui lòng dùng mẫu hoặc đặt tên cột là “Mã vật tư, Tên vật tư”.',
        '匯入完成：新增 ': 'Nhập hoàn tất: thêm mới ',
        ' 筆，更新 ': ' mục, cập nhật ',
        '。': '。',
        '檔案讀取失敗：': 'Đọc tệp thất bại: ',
        '新增單筆備品': 'Thêm một vật tư',
        '期初庫存': 'Tồn kho ban đầu',
        '新增備品': 'Thêm vật tư',
        '備品編號與名稱為必填。': 'Mã vật tư và tên vật tư là bắt buộc.',
        '新增成功。': 'Thêm mới thành công。',
        '備品編號已存在。': 'Mã vật tư đã tồn tại.',
        '失效與恢復': 'Ngừng sử dụng và khôi phục',
        '失效備品': 'Vật tư ngừng sử dụng',
        '確認失效': 'Xác nhận ngừng sử dụng',
        '備品已設為失效；歷史異動紀錄保留。': 'Vật tư đã được chuyển sang trạng thái ngừng sử dụng; lịch sử giao dịch vẫn được giữ lại.',
        '目前沒有可設為失效的備品。': 'Hiện không có vật tư nào có thể chuyển sang trạng thái ngừng sử dụng.',
        '恢復備品': 'Khôi phục vật tư',
        '確認恢復': 'Xác nhận khôi phục',
        '備品已恢復啟用。': 'Vật tư đã được kích hoạt lại.',
        '目前沒有可恢復的失效備品。': 'Hiện không có vật tư ngừng sử dụng nào để khôi phục.',
        '刪除料號': 'Xóa mã vật tư',
        '管理員可強制刪除已失效料號；若該料號有庫存異動紀錄，相關異動紀錄也會一併永久刪除。': 'Quản trị viên có thể xóa mã vật tư đã ngừng sử dụng. Nếu mã này có lịch sử giao dịch, các giao dịch liên quan cũng sẽ bị xóa vĩnh viễn.',
        '一般操作人員不能刪除有庫存異動紀錄的料號；請由系統管理員處理。': 'Người dùng thông thường không thể xóa mã vật tư có lịch sử giao dịch; vui lòng yêu cầu quản trị viên hệ thống xử lý.',
        '請先勾選確認框，再刪除料號。': 'Vui lòng đánh dấu ô xác nhận trước khi xóa mã vật tư.',
        '找不到此料號，請重新整理後再試。': 'Không tìm thấy mã vật tư này. Vui lòng làm mới và thử lại.',
        '只能刪除已失效的備品；正常啟用中的備品不能刪除。': 'Chỉ có thể xóa vật tư đã ngừng sử dụng; không thể xóa vật tư đang hoạt động.',
        '目前沒有可刪除的失效備品。': 'Hiện không có vật tư ngừng sử dụng nào có thể xóa.',
        '人員與權限': 'Nhân sự và phân quyền',
        '本模組只管理登入帳號；帳號建立後立即生效，刪除後立即無法登入。一般員工可在登入畫面自行建立員工權限帳號。': 'Mô-đun này chỉ quản lý tài khoản đăng nhập. Tài khoản có hiệu lực ngay sau khi tạo và không thể đăng nhập sau khi bị xóa. Nhân viên có thể tự tạo tài khoản quyền nhân viên tại màn hình đăng nhập.',
        '建立 / 更新登入帳號': 'Tạo / cập nhật tài khoản đăng nhập',
        '操作': 'Thao tác',
        '更新帳號': 'Cập nhật tài khoản',
        '選擇要更新的帳號': 'Chọn tài khoản cần cập nhật',
        '顯示名稱自動使用工號。': 'Tên hiển thị tự động sử dụng mã nhân viên.',
        '啟用帳號': 'Kích hoạt tài khoản',
        '帳號、顯示名稱、部門不可空白。': 'Tài khoản, tên hiển thị và bộ phận không được để trống.',
        '建立帳號時，密碼至少需要 10 個字元。': 'Khi tạo tài khoản, mật khẩu phải có ít nhất 10 ký tự.',
        '密碼至少需要 10 個字元，或留空以保留原密碼。': 'Mật khẩu phải có ít nhất 10 ký tự hoặc để trống để giữ mật khẩu cũ.',
        '帳號已儲存。': 'Đã lưu tài khoản.',
        '此帳號已存在，請檢查帳號名稱。': 'Tài khoản này đã tồn tại. Vui lòng kiểm tra tên tài khoản.',
        '登入帳號清單': 'Danh sách tài khoản đăng nhập',
        '權限': 'Quyền hạn',
        '刪除登入帳號': 'Xóa tài khoản đăng nhập',
        '刪除後帳號立即無法登入。不能刪除目前登入帳號，也不能刪除最後一個啟用中的系統管理員。': 'Sau khi xóa, tài khoản không thể đăng nhập ngay. Không thể xóa tài khoản đang đăng nhập hoặc quản trị viên hệ thống đang hoạt động cuối cùng.',
        '刪除帳號': 'Xóa tài khoản',
        '請先勾選確認框。': 'Vui lòng đánh dấu ô xác nhận trước.',
        '不能刪除目前登入的帳號。': 'Không thể xóa tài khoản đang đăng nhập.',
        '找不到此帳號，請重新整理後再試。': 'Không tìm thấy tài khoản này. Vui lòng làm mới và thử lại.',
        '不能刪除最後一個啟用中的系統管理員帳號。': 'Không thể xóa tài khoản quản trị viên hệ thống đang hoạt động cuối cùng.',
        '已刪除，立即失效。': 'đã bị xóa và vô hiệu hóa ngay.',
        '備份與還原': 'Sao lưu và khôi phục',
        '備份檔含有完整庫存與異動紀錄，請存放在公司核准且有存取權限的位置。還原會覆蓋目前資料庫，請先備份目前版本。': 'Tệp sao lưu chứa toàn bộ tồn kho và lịch sử giao dịch. Hãy lưu tại vị trí được công ty phê duyệt và có kiểm soát truy cập. Khôi phục sẽ ghi đè cơ sở dữ liệu hiện tại; vui lòng sao lưu trước.',
        '立即建立資料庫備份': 'Tạo bản sao lưu cơ sở dữ liệu ngay',
        '現有備份': 'Bản sao lưu hiện có',
        '還原資料庫備份（僅管理員）': 'Khôi phục bản sao lưu cơ sở dữ liệu (chỉ quản trị viên)',
        '確認還原，覆蓋目前資料庫': 'Xác nhận khôi phục và ghi đè cơ sở dữ liệu hiện tại',
        '備份檔完整性檢查失敗，未還原。': 'Kiểm tra tính toàn vẹn của tệp sao lưu thất bại; chưa khôi phục.',
        '還原完成。請重新登入並核對庫存。': 'Khôi phục hoàn tất. Vui lòng đăng nhập lại và kiểm tra tồn kho.',
        '還原失敗：': 'Khôi phục thất bại: ',
        '建立備份': 'Tạo bản sao lưu',
        '優先級': 'Mức ưu tiên',
        '缺少數量': 'Số lượng thiếu',
        '建議補貨量': 'Số lượng đề xuất bổ sung',
        '異動前': 'Trước giao dịch',
        '異動後': 'Sau giao dịch',
        '異動前庫存': 'Tồn kho trước giao dịch',
        '異動後庫存': 'Tồn kho sau giao dịch',
        '參考單號': 'Mã tham chiếu',
        '關聯設備編號': 'Mã thiết bị liên quan',
        '最低庫存': 'Tồn kho tối thiểu',
        '目標庫存': 'Tồn kho mục tiêu',
        '儲位': 'Vị trí lưu kho',
        '備註': 'Ghi chú',
        '規格': 'Quy cách',
        '單位': 'Đơn vị',
        '單位成本': 'Đơn giá',
        '類別': 'Danh mục',
        '目前庫存': 'Tồn kho hiện tại',
        '備品名稱': 'Tên vật tư',
        '備品編號': 'Mã vật tư',
        '紀錄編號': 'Mã giao dịch',
        '時間': 'Thời gian',
        '類型': 'Loại giao dịch',
        '領用/相關人員': 'Người nhận / người liên quan',
        '操作帳號': 'Tài khoản thao tác',
        '原因': 'Lý do',
        '系統管理員': 'Quản trị viên hệ thống',
        '管理員權限': 'Quyền quản lý',
        '員工權限': 'Quyền nhân viên',
        '入庫': 'Nhập kho',
        '出庫': 'Xuất kho',
        '盤點增加': 'Tăng sau kiểm kê',
        '盤點減少': 'Giảm sau kiểm kê',
        '設備維修': 'Bảo trì thiết bị',
        '採購入庫': 'Nhập kho mua hàng',
        '請選擇': 'Vui lòng chọn',
        '確認': 'Xác nhận',
        '取消': 'Hủy',
        '儲存': 'Lưu',
        '新增': 'Thêm mới',
        '刪除': 'Xóa',
        '更新': 'Cập nhật',
        '匯出': 'Xuất dữ liệu',
        '下載': 'Tải xuống',
        '三大功能模塊': 'Ba mô-đun chức năng chính',
        '請選擇要使用的管理模塊。': 'Vui lòng chọn mô-đun quản lý muốn sử dụng.',
        '管理人員基本資料、技能矩陣、技能等級、證照與培訓紀錄。': 'Quản lý hồ sơ nhân sự, ma trận kỹ năng, cấp độ kỹ năng, chứng chỉ và hồ sơ đào tạo.',
        '管理設備台帳、保養週期、維修工時、設備異常、原因與處理進度。': 'Quản lý danh mục thiết bị, chu kỳ bảo trì, thời gian sửa chữa, sự cố thiết bị, nguyên nhân và tiến độ xử lý.',
        '使用已完成的庫存管理、入庫出庫、低庫存預警、報表及備份功能。': 'Sử dụng các chức năng đã hoàn thiện: quản lý tồn kho, nhập/xuất kho, cảnh báo tồn kho thấp, báo cáo và sao lưu.',
        '進入人員管理': 'Vào quản lý nhân sự',
        '進入設備管理': 'Vào quản lý thiết bị',
        '進入備品管理': 'Vào quản lý vật tư',
        '人員管理模塊': 'Mô-đun quản lý nhân sự',
        '設備管理模塊': 'Mô-đun quản lý thiết bị',
        '備品管理模塊': 'Mô-đun quản lý vật tư',
        '模塊首頁': 'Trang chủ mô-đun',
        '人員總覽': 'Tổng quan nhân sự',
        '人員資料與技能': 'Hồ sơ nhân sự và kỹ năng',
        '技能項目管理': 'Quản lý danh mục kỹ năng',
        '人員技能矩陣': 'Ma trận kỹ năng nhân sự',
        '培訓紀錄': 'Hồ sơ đào tạo',
        '考試紀錄': 'Hồ sơ thi/kiểm tra',
        '設備總覽': 'Tổng quan thiết bị',
        '設備資料管理': 'Quản lý dữ liệu thiết bị',
        '保養計畫與紀錄': 'Kế hoạch và hồ sơ bảo trì',
        '設備異常紀錄': 'Hồ sơ sự cố thiết bị',
        '功能選單': 'Danh mục chức năng',
        '登出': 'Đăng xuất',
    }
}
def tr_text(value):
    if not isinstance(value, str):
        return value
    lang = st.session_state.get("ui_language", "中文")
    table = UI_TEXT.get(lang, UI_TEXT["中文"])
    if value in table:
        return table[value]
    # Replace known labels inside longer UI strings, longest phrase first.
    if lang == "越南語":
        for source_text in sorted(table.keys(), key=len, reverse=True):
            if source_text and source_text in value and table[source_text] != source_text:
                value = value.replace(source_text, table[source_text])
    return value

def _wrap_streamlit_text_api(name):
    original = getattr(st, name, None)
    if original is None or getattr(original, "_bilingual_wrapped", False):
        return

    def wrapped(*args, **kwargs):
        args = list(args)
        kwargs = dict(kwargs)
        format_func = kwargs.get("format_func")

        # Streamlit's option values must remain unchanged for the app's logic.
        # Only the visible option labels are translated via format_func.
        if name in ("selectbox", "radio", "multiselect"):
            if format_func is None:
                format_func = lambda x: tr_text(x) if isinstance(x, str) else x
            kwargs["format_func"] = format_func

        args = [tr_text(x) if isinstance(x, str) else x for x in args]
        kwargs = {
            k: (tr_text(v) if isinstance(v, str) else v)
            for k, v in kwargs.items()
            if k != "format_func"
        }
        if name in ("selectbox", "radio", "multiselect"):
            kwargs["format_func"] = format_func
        return original(*args, **kwargs)

    wrapped._bilingual_wrapped = True
    setattr(st, name, wrapped)

for _api_name in (
    "title", "header", "subheader", "caption", "markdown", "write", "text",
    "info", "success", "warning", "error", "exception", "button", "text_input",
    "text_area", "number_input", "selectbox", "multiselect", "radio", "checkbox",
    "form_submit_button", "download_button", "file_uploader", "date_input",
    "time_input", "metric", "divider", "expander", "tabs", "data_editor",
):
    _wrap_streamlit_text_api(_api_name)

# Translate table column headers and visible string values in bilingual mode.
# Streamlit reruns this script on every interaction. Preserve the true original
# dataframe function so reruns never wrap _bilingual_dataframe inside itself.
_current_dataframe = st.dataframe
_original_dataframe = getattr(
    _current_dataframe, "_bilingual_original_dataframe", _current_dataframe
)

def _bilingual_dataframe(data=None, *args, **kwargs):
    if st.session_state.get("ui_language", "中文") == "越南語" and isinstance(data, pd.DataFrame):
        data = data.copy()
        data.columns = [tr_text(str(c)) for c in data.columns]
        for col in data.columns:
            if data[col].dtype == object:
                data[col] = data[col].map(lambda x: tr_text(x) if isinstance(x, str) else x)
    return _original_dataframe(data, *args, **kwargs)

_bilingual_dataframe._bilingual_original_dataframe = _original_dataframe
_bilingual_dataframe._bilingual_wrapped = True
st.dataframe = _bilingual_dataframe

# Sidebar also uses Streamlit APIs; translate labels and visible option values.
for _api_name in (
    "title", "header", "subheader", "caption", "markdown", "write", "text",
    "info", "success", "warning", "error", "button", "text_input", "selectbox",
    "radio", "checkbox", "download_button", "expander",
):
    _sidebar_api = getattr(st.sidebar, _api_name, None)
    if _sidebar_api is not None and not getattr(_sidebar_api, "_bilingual_wrapped", False):
        def _make_sidebar_wrapper(original, api_name):
            def _wrapped(*args, **kwargs):
                args = list(args)
                kwargs = dict(kwargs)
                format_func = kwargs.get("format_func")
                if api_name in ("selectbox", "radio"):
                    if format_func is None:
                        format_func = lambda x: tr_text(x) if isinstance(x, str) else x
                    kwargs["format_func"] = format_func
                args = [tr_text(x) if isinstance(x, str) else x for x in args]
                kwargs = {
                    k: (tr_text(v) if isinstance(v, str) else v)
                    for k, v in kwargs.items()
                    if k != "format_func"
                }
                if api_name in ("selectbox", "radio"):
                    kwargs["format_func"] = format_func
                return original(*args, **kwargs)
            _wrapped._bilingual_wrapped = True
            return _wrapped
        setattr(st.sidebar, _api_name, _make_sidebar_wrapper(_sidebar_api, _api_name))

def bilingual_sidebar():
    # Keep the language selector fixed at the top of the sidebar.
    selected = st.sidebar.selectbox(
        "語言 / Ngôn ngữ",
        ["中文", "越南語"],
        key="ui_language",
        format_func=lambda x: "中文 / Tiếng Trung" if x == "中文" else "越南語 / Tiếng Việt",
    )
    return selected
# ===== 中越雙語介面結束 =====



VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def now_str():
    """Return current Vietnam local time for new audit and inventory records."""
    return datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")



def connect():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "缺少 DATABASE_URL 環境變數，請在 Render 的 Environment 中設定。"
        )

    return psycopg.connect(
        database_url,
        sslmode="require",
        options="-c search_path=spares,public",
        row_factory=dict_row,
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
    # Tables are provisioned by the included SQL script. An empty database is allowed;
    # the first system-admin account is created from environment variables below.
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
                username = os.environ.get("SPARES_ADMIN_USERNAME", "admin").strip()
                password = os.environ.get("SPARES_ADMIN_PASSWORD", "")
                if len(password) < 12:
                    raise RuntimeError(
                        "資料庫尚無帳號。請在 Render 環境變數設定 SPARES_ADMIN_PASSWORD（至少 12 字元），"
                        "並可設定 SPARES_ADMIN_USERNAME。"
                    )
                salt, digest = hash_password(password)
                cur.execute(
                    """INSERT INTO users(username,display_name,salt,password_hash,role,active,created_at)
                       VALUES(%s,%s,%s,%s,'system_admin',1,%s)
                       ON CONFLICT(username) DO NOTHING""",
                    (username, username, salt, digest, now_str()),
                )
                cur.execute(
                    """INSERT INTO staff(name,department,active) VALUES(%s,%s,1)
                       ON CONFLICT(name) DO NOTHING""",
                    (username, "生技"),
                )
                con.commit()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS spares.personnel_profiles (
                                    id BIGSERIAL PRIMARY KEY,
                                    employee_code TEXT NOT NULL UNIQUE,
                                    full_name TEXT NOT NULL,
                                    department TEXT DEFAULT '',
                                    position TEXT DEFAULT '',
                                    hire_date TEXT DEFAULT '',
                                    skills TEXT DEFAULT '',
                                    skill_level TEXT DEFAULT '待評估',
                                    certifications TEXT DEFAULT '',
                                    training_records TEXT DEFAULT '',
                                    phone TEXT DEFAULT '',
                                    status TEXT NOT NULL DEFAULT '在職',
                                    notes TEXT DEFAULT '',
                                    created_at TEXT NOT NULL,
                                    updated_at TEXT NOT NULL
                                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spares.skill_catalog (
                                    id BIGSERIAL PRIMARY KEY,
                                    skill_name TEXT NOT NULL UNIQUE,
                                    skill_category TEXT DEFAULT '',
                                    description TEXT DEFAULT '',
                                    active INTEGER NOT NULL DEFAULT 1,
                                    created_at TEXT NOT NULL
                                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spares.personnel_skill_records (
                                    id BIGSERIAL PRIMARY KEY,
                                    employee_code TEXT NOT NULL,
                                    skill_name TEXT NOT NULL,
                                    skill_level TEXT NOT NULL DEFAULT '待評估',
                                    assessed_date TEXT DEFAULT '',
                                    assessed_by TEXT DEFAULT '',
                                    notes TEXT DEFAULT '',
                                    created_at TEXT NOT NULL,
                                    updated_at TEXT NOT NULL,
                                    UNIQUE(employee_code, skill_name)
                                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spares.personnel_training_records (
                                    id BIGSERIAL PRIMARY KEY,
                                    employee_code TEXT NOT NULL,
                                    training_date TEXT NOT NULL,
                                    training_topic TEXT NOT NULL,
                                    training_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
                                    result TEXT DEFAULT '',
                                    trainer TEXT DEFAULT '',
                                    notes TEXT DEFAULT '',
                                    created_by TEXT NOT NULL,
                                    created_at TEXT NOT NULL
                                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spares.personnel_exam_records (
                                    id BIGSERIAL PRIMARY KEY,
                                    employee_code TEXT NOT NULL,
                                    exam_date TEXT NOT NULL,
                                    exam_name TEXT NOT NULL,
                                    skill_name TEXT DEFAULT '',
                                    score DOUBLE PRECISION DEFAULT 0,
                                    max_score DOUBLE PRECISION DEFAULT 100,
                                    passed TEXT DEFAULT '待判定',
                                    examiner TEXT DEFAULT '',
                                    notes TEXT DEFAULT '',
                                    created_by TEXT NOT NULL,
                                    created_at TEXT NOT NULL
                                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spares.equipment (
                                    id BIGSERIAL PRIMARY KEY,
                                    equipment_code TEXT NOT NULL UNIQUE,
                                    equipment_name TEXT NOT NULL,
                                    model TEXT DEFAULT '',
                                    location TEXT DEFAULT '',
                                    department TEXT DEFAULT '',
                                    owner TEXT DEFAULT '',
                                    install_date TEXT DEFAULT '',
                                    status TEXT NOT NULL DEFAULT '正常',
                                    maintenance_interval_days INTEGER NOT NULL DEFAULT 30,
                                    last_maintenance_date TEXT DEFAULT '',
                                    next_maintenance_date TEXT DEFAULT '',
                                    notes TEXT DEFAULT '',
                                    created_at TEXT NOT NULL,
                                    updated_at TEXT NOT NULL
                                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spares.maintenance_records (
                                    id BIGSERIAL PRIMARY KEY,
                                    equipment_id BIGINT NOT NULL REFERENCES spares.equipment(id),
                                    maintenance_date TEXT NOT NULL,
                                    maintenance_type TEXT NOT NULL DEFAULT '定期保養',
                                    technician TEXT DEFAULT '',
                                    duration_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
                                    result TEXT DEFAULT '',
                                    parts_used TEXT DEFAULT '',
                                    next_maintenance_date TEXT DEFAULT '',
                                    notes TEXT DEFAULT '',
                                    created_by TEXT NOT NULL,
                                    created_at TEXT NOT NULL
                                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spares.equipment_abnormalities (
                                    id BIGSERIAL PRIMARY KEY,
                                    equipment_id BIGINT NOT NULL REFERENCES spares.equipment(id),
                                    occurred_at TEXT NOT NULL,
                                    severity TEXT NOT NULL DEFAULT '一般',
                                    symptom TEXT NOT NULL,
                                    root_cause TEXT DEFAULT '',
                                    action_taken TEXT DEFAULT '',
                                    downtime_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
                                    status TEXT NOT NULL DEFAULT '未結案',
                                    closed_at TEXT DEFAULT '',
                                    reported_by TEXT NOT NULL,
                                    created_at TEXT NOT NULL,
                                    handler_name TEXT DEFAULT '',
                                    handling_started_at TEXT DEFAULT '',
                                    handling_finished_at TEXT DEFAULT '',
                                    handling_hours DOUBLE PRECISION NOT NULL DEFAULT 0
                                )
            """)
            cur.execute("""
                ALTER TABLE spares.equipment_abnormalities
                ADD COLUMN IF NOT EXISTS handler_name TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS handling_started_at TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS handling_finished_at TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS handling_hours DOUBLE PRECISION NOT NULL DEFAULT 0
            """)
            con.commit()

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

ROLE_LABELS = {
    "system_admin": "系統管理員",
    "manager": "管理員權限",
    "employee": "員工權限",
    # 舊版資料庫使用的角色名稱，保留相容顯示。
    "admin": "系統管理員（舊版角色）",
    "operator": "員工權限（舊版角色）",
}


def normalize_role(role):
    """Map legacy database role values to the current three-role model."""
    return {
        "admin": "system_admin",
        "operator": "employee",
        "system_admin": "system_admin",
        "manager": "manager",
        "employee": "employee",
    }.get(str(role or "").strip(), "employee")

def require_system_admin():
    if st.session_state.user["role"] != "system_admin":
        st.error("此功能僅限系統管理員使用。")
        st.stop()

def require_manager_or_higher():
    if st.session_state.user["role"] not in ("system_admin", "manager"):
        st.error("此功能需要管理員或系統管理員權限。")
        st.stop()

def require_admin():
    require_system_admin()


def can_manage_modules():
    return st.session_state.user.get("role") in ("system_admin", "manager")

def show_module_permission_note():
    role = st.session_state.user.get("role", "employee")
    if role == "system_admin":
        st.caption("目前權限：系統管理員｜可查看及管理模塊資料。")
    elif role == "manager":
        st.caption("目前權限：管理員｜可查看及新增／管理模塊資料。")
    else:
        st.caption("目前權限：員工｜可查看資料，並可新增設備、保養及設備異常紀錄。")

def _navigate_module(module_name, page_name):
    st.session_state["main_module"] = module_name
    st.session_state[f"module_page_{module_name}"] = page_name


def login_screen():
    st.title("📦 部門備品管理系統")
    st.caption("共用庫存、異動追蹤、低庫存預警")
    with st.form("login_form"):
        username = st.text_input("登入帳號")
        password = st.text_input("密碼", type="password")
        submitted = st.form_submit_button("登入", use_container_width=True)
    if submitted:
        with connect() as con:
            user = con.execute("SELECT * FROM users WHERE username=%s AND active=1", (username.strip(),)).fetchone()
        if user and verify_password(password, user["salt"], user["password_hash"]):
            # 相容既有資料庫：舊版 admin/operator 角色映射到新權限模型。
            user_data = dict(user)
            user_data["role"] = normalize_role(user_data.get("role"))
            st.session_state.user = user_data
            log_action(username.strip(), "登入", "登入成功")
            st.rerun()
        else:
            st.error("帳號或密碼錯誤，或帳號已停用。")
    st.info("若尚無帳號，請由登入畫面的員工帳號註冊功能建立員工帳號；系統管理員帳號由部署環境變數初始化。")

    st.divider()
    st.subheader("建立員工帳號")
    st.caption("輸入工號建立員工權限帳號；密碼至少 10 個字元，建立後立即生效。")
    with st.form("self_register_form"):
        reg_username = st.text_input("工號", key="reg_username")
        reg_password = st.text_input("密碼（至少 10 個字元）", type="password", key="reg_password")
        reg_department = st.selectbox("部門", ["生技", "品保", "製造"], key="reg_department")
        reg_submit = st.form_submit_button("建立帳號", use_container_width=True)
    if reg_submit:
        if not reg_username.strip() or len(reg_password) < 10:
            st.error("工號不可空白，密碼至少 10 個字元。")
        else:
            salt, digest = hash_password(reg_password)
            try:
                with connect() as con:
                    con.execute(
                        """INSERT INTO users(username,display_name,salt,password_hash,role,active,created_at)
                           VALUES(%s,%s,%s,%s,'employee',1,%s)""",
                        (reg_username.strip(), reg_username.strip(), salt, digest, now_str()),
                    )
                    con.execute(
                        """INSERT INTO staff(name,department,active) VALUES(%s,%s,1)
                           ON CONFLICT(name) DO UPDATE SET department=excluded.department,active=1""",
                        (reg_username.strip(), reg_department),
                    )
                    con.commit()
                log_action(reg_username.strip(), "自行建立帳號", "employee")
                st.success("帳號建立成功，現在即可登入。")
            except psycopg.IntegrityError:
                st.error("此工號已存在，請使用其他工號。")

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
        "單位":"個","最低庫存":3,"目標庫存":10,"單價":0,"期初庫存":5,"庫存金額":""
    }])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="備品清單")
        ws = writer.sheets["備品清單"]
        ws["J2"] = "=H2*I2"
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cells in ws.columns:
            letter = cells[0].column_letter
            max_len = max(len(str(c.value or "")) for c in cells)
            ws.column_dimensions[letter].width = min(max(max_len + 4, 12), 28)
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
        with st.expander("修改我的密碼", expanded=False):
            change_own_password()

        st.title("🏭 部門管理系統")
        st.write(f"登入：**{user['display_name']}**")
        st.caption("權限：" + ROLE_LABELS.get(user["role"], user["role"]))

        modules = ["模塊首頁", "人員管理模塊", "設備管理模塊", "備品管理模塊"]
        module = st.radio("三大功能模塊", modules, key="main_module")
        if module == "模塊首頁":
            pages = ["模塊首頁"]
        elif module == "人員管理模塊":
            if can_manage_modules():
                pages = ["人員總覽", "人員資料與技能", "技能項目管理", "人員技能矩陣", "培訓紀錄", "考試紀錄"]
            else:
                pages = ["人員總覽", "人員資料與技能", "人員技能矩陣", "培訓紀錄", "考試紀錄"]
        elif module == "設備管理模塊":
            pages = ["設備總覽", "設備資料管理", "保養計畫與紀錄", "設備異常紀錄"]
        else:
            if user["role"] == "system_admin":
                pages = [
                    "總覽儀表板","入庫 / 出庫","庫存查詢","缺少清單","月報與匯出",
                    "異動紀錄","備品資料管理","人員與權限","備份與還原"
                ]
            elif user["role"] == "manager":
                pages = ["總覽儀表板","入庫 / 出庫","庫存查詢","缺少清單","月報與匯出","備品資料管理"]
            else:
                pages = ["入庫 / 出庫"]
        page = st.radio("功能選單", pages, key=f"module_page_{module}")
        if st.button("登出", use_container_width=True):
            log_action(user["username"], "登出", "使用者登出")
            del st.session_state.user
            st.rerun()

    if page == "模塊首頁":
        st.title("🏭 部門管理系統")
        st.subheader("三大功能模塊")
        st.caption("請選擇要使用的管理模塊。")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 👥 人員管理模塊")
            st.write("管理人員基本資料、技能矩陣、技能等級、證照與培訓紀錄。")
            st.button("進入人員管理", use_container_width=True,
                      on_click=_navigate_module, args=("人員管理模塊", "人員總覽"))
        with c2:
            st.markdown("### 🛠️ 設備管理模塊")
            st.write("管理設備台帳、保養週期、維修工時、設備異常、原因與處理進度。")
            st.button("進入設備管理", use_container_width=True,
                      on_click=_navigate_module, args=("設備管理模塊", "設備總覽"))
        with c3:
            st.markdown("### 📦 備品管理模塊")
            st.write("使用已完成的庫存管理、入庫出庫、低庫存預警、報表及備份功能。")
            st.button("進入備品管理", use_container_width=True,
                      on_click=_navigate_module, args=("備品管理模塊", "總覽儀表板"))

    elif page == "人員總覽":
        st.title("人員管理模塊")
        show_module_permission_note()
        with connect() as con:
            people = query_df("SELECT employee_code AS 員工編號,full_name AS 姓名,department AS 部門,position AS 職位,skill_level AS 技能等級,status AS 在職狀態 FROM personnel_profiles ORDER BY department,employee_code", con)
            skill_count = con.execute("SELECT COUNT(*) AS n FROM skill_catalog WHERE active=1").fetchone()["n"]
            people_count = con.execute("SELECT COUNT(*) AS n FROM personnel_profiles WHERE status='在職'").fetchone()["n"]
            training_count = con.execute("SELECT COUNT(*) AS n FROM personnel_profiles WHERE COALESCE(training_records,'')<>''").fetchone()["n"]
        a,b,c = st.columns(3)
        a.metric("在職人員", people_count)
        b.metric("技能項目", skill_count)
        c.metric("有培訓紀錄人員", training_count)
        st.subheader("人員技能分布")
        if people.empty:
            st.info("請先到「人員資料與技能」新增人員資料。")
        else:
            st.dataframe(people, use_container_width=True, hide_index=True)

    elif page == "人員資料與技能":
        st.title("人員資料與技能")
        show_module_permission_note()
        if can_manage_modules():
            with st.form("personnel_profile_form"):
                a,b = st.columns(2)
                employee_code = a.text_input("員工編號 *")
                full_name = b.text_input("姓名 *")
                c,d = st.columns(2)
                department = c.text_input("部門", value="技術機械部")
                position = d.text_input("職位")
                e,f = st.columns(2)
                hire_date = e.date_input("到職日期", value=None)
                phone = f.text_input("聯絡電話")
                skill_level = st.selectbox("綜合技能等級", ["待評估","初級 (1-2)","中級 (3-5)","熟練 (6-8)","專家 (9-10)"])
                notes = st.text_area("備註")
                save_person = st.form_submit_button("新增人員資料")
            if save_person:
                if not employee_code.strip() or not full_name.strip():
                    st.error("員工編號與姓名為必填。")
                else:
                    try:
                        with connect() as con:
                            con.execute("""INSERT INTO personnel_profiles(employee_code,full_name,department,position,hire_date,skills,skill_level,certifications,training_records,phone,status,notes,created_at,updated_at)
                                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (employee_code.strip(),full_name.strip(),department.strip(),position.strip(),
                                 hire_date.isoformat() if hire_date else "","",skill_level,"",
                                 "",phone.strip(),"在職",notes.strip(),now_str(),now_str()))
                            con.execute("""INSERT INTO staff(name,department,active) VALUES(%s,%s,1)
                                ON CONFLICT(name) DO UPDATE SET department=excluded.department,active=1""",
                                (full_name.strip(),department.strip()))
                            con.commit()
                        log_action(user["username"], "新增人員資料", employee_code.strip())
                        st.success("人員資料已儲存。")
                        st.rerun()
                    except psycopg.errors.UniqueViolation:
                        st.error("員工編號已存在。")
        else:
            st.info("目前為檢視權限；新增或修改人員資料需管理員權限。")
        with connect() as con:
            df = query_df("SELECT employee_code AS 員工編號,full_name AS 姓名,department AS 部門,position AS 職位,hire_date AS 到職日期,skills AS 技能,skill_level AS 技能等級,certifications AS 證照,training_records AS 培訓紀錄,phone AS 聯絡電話,status AS 在職狀態,notes AS 備註 FROM personnel_profiles ORDER BY employee_code", con)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if can_manage_modules():
            st.divider()
            st.subheader("修改人員資料（管理權限）")
            with connect() as con:
                editable_people = con.execute(
                    "SELECT employee_code,full_name,department,position,hire_date,phone,skill_level,status,notes FROM personnel_profiles ORDER BY employee_code"
                ).fetchall()
            if editable_people:
                edit_people_map = {f"{r['employee_code']} | {r['full_name']}": r for r in editable_people}
                selected_edit_person = st.selectbox("選擇要修改的人員", list(edit_people_map), key="edit_person_select")
                selected_person_row = edit_people_map[selected_edit_person]
                with st.form("edit_personnel_profile_form"):
                    a,b = st.columns(2)
                    edit_employee_code = a.text_input("員工編號", value=selected_person_row["employee_code"], disabled=True)
                    edit_full_name = b.text_input("姓名 *", value=selected_person_row["full_name"] or "")
                    c,d = st.columns(2)
                    edit_department = c.text_input("部門", value=selected_person_row["department"] or "")
                    edit_position = d.text_input("職位", value=selected_person_row["position"] or "")
                    e,f = st.columns(2)
                    edit_hire_date = e.text_input("到職日期（YYYY-MM-DD）", value=selected_person_row["hire_date"] or "")
                    edit_phone = f.text_input("聯絡電話", value=selected_person_row["phone"] or "")
                    skill_levels = ["待評估","初級 (1-2)","中級 (3-5)","熟練 (6-8)","專家 (9-10)"]
                    current_level = selected_person_row["skill_level"] or "待評估"
                    edit_skill_level = st.selectbox("綜合技能等級", skill_levels, index=skill_levels.index(current_level) if current_level in skill_levels else 0)
                    edit_status = st.selectbox("在職狀態", ["在職", "離職", "留停"], index=["在職", "離職", "留停"].index(selected_person_row["status"]) if selected_person_row["status"] in ["在職", "離職", "留停"] else 0)
                    edit_notes = st.text_area("備註", value=selected_person_row["notes"] or "")
                    save_person_changes = st.form_submit_button("儲存人員修改")
                if save_person_changes:
                    if not edit_full_name.strip():
                        st.error("姓名為必填。")
                    elif edit_hire_date.strip() and (len(edit_hire_date.strip()) != 10 or edit_hire_date.strip()[4:5] != "-" or edit_hire_date.strip()[7:8] != "-"):
                        st.error("到職日期請使用 YYYY-MM-DD 格式，或留空。")
                    else:
                        old_name = selected_person_row["full_name"]
                        try:
                            with connect() as con:
                                con.execute("""UPDATE personnel_profiles SET full_name=%s,department=%s,position=%s,hire_date=%s,phone=%s,skill_level=%s,status=%s,notes=%s,updated_at=%s WHERE employee_code=%s""",
                                    (edit_full_name.strip(),edit_department.strip(),edit_position.strip(),edit_hire_date.strip(),edit_phone.strip(),edit_skill_level,edit_status,edit_notes.strip(),now_str(),edit_employee_code))
                                con.execute("""UPDATE staff SET active=0 WHERE name=%s AND %s<>%s
                                    AND NOT EXISTS (SELECT 1 FROM personnel_profiles WHERE full_name=%s)""",
                                    (old_name,edit_full_name.strip(),old_name,old_name))
                                con.execute("""INSERT INTO staff(name,department,active) VALUES(%s,%s,%s)
                                    ON CONFLICT(name) DO UPDATE SET department=excluded.department,active=excluded.active""",
                                    (edit_full_name.strip(),edit_department.strip(),1 if edit_status == "在職" else 0))
                                con.commit()
                            log_action(user["username"], "修改人員資料", edit_employee_code)
                            st.success("人員資料已更新。")
                            st.rerun()
                        except psycopg.errors.UniqueViolation:
                            st.error("更新失敗：資料與現有紀錄重複，請檢查員工編號或姓名。")
            st.divider()
            st.subheader("刪除人員（管理權限）")
            with connect() as con:
                people_to_delete = con.execute(
                    "SELECT employee_code,full_name FROM personnel_profiles ORDER BY employee_code"
                ).fetchall()
            if people_to_delete:
                person_map = {f"{r['employee_code']} | {r['full_name']}": r["employee_code"] for r in people_to_delete}
                selected_delete_person = st.selectbox("選擇要刪除的人員", list(person_map), key="delete_person_select")
                confirm_delete_person = st.checkbox(
                    "我確認刪除此人員及其技能、培訓、考試資料；此操作無法復原",
                    key="confirm_delete_person"
                )
                if st.button("永久刪除人員", type="secondary"):
                    if not confirm_delete_person:
                        st.error("請先勾選確認框。")
                    else:
                        employee_code_to_delete = person_map[selected_delete_person]
                        with connect() as con:
                            person_row = con.execute(
                                "SELECT full_name FROM personnel_profiles WHERE employee_code=%s",
                                (employee_code_to_delete,)
                            ).fetchone()
                            if person_row:
                                con.execute("DELETE FROM personnel_skill_records WHERE employee_code=%s", (employee_code_to_delete,))
                                con.execute("DELETE FROM personnel_training_records WHERE employee_code=%s", (employee_code_to_delete,))
                                con.execute("DELETE FROM personnel_exam_records WHERE employee_code=%s", (employee_code_to_delete,))
                                con.execute("DELETE FROM personnel_profiles WHERE employee_code=%s", (employee_code_to_delete,))
                                # Only deactivate the spare-parts staff choice if no remaining profile uses the same name.
                                still_exists = con.execute("SELECT 1 FROM personnel_profiles WHERE full_name=%s", (person_row["full_name"],)).fetchone()
                                if not still_exists:
                                    con.execute("UPDATE staff SET active=0 WHERE name=%s", (person_row["full_name"],))
                                con.commit()
                        log_action(user["username"], "刪除人員資料", employee_code_to_delete)
                        st.success("人員及其技能、培訓、考試資料已刪除。")
                        st.rerun()

    elif page == "技能項目管理":
        st.title("技能項目管理")
        show_module_permission_note()
        if can_manage_modules():
            with st.form("skill_catalog_form"):
                skill_name = st.text_input("技能名稱 *")
                skill_category = st.text_input("技能類別")
                skill_description = st.text_area("技能說明")
                add_skill = st.form_submit_button("新增技能項目")
            if add_skill:
                if not skill_name.strip():
                    st.error("技能名稱為必填。")
                else:
                    try:
                        with connect() as con:
                            con.execute("INSERT INTO skill_catalog(skill_name,skill_category,description,active,created_at) VALUES(%s,%s,%s,1,%s)",
                                        (skill_name.strip(),skill_category.strip(),skill_description.strip(),now_str()))
                            con.commit()
                        log_action(user["username"], "新增技能項目", skill_name.strip())
                        st.success("技能項目已新增。")
                        st.rerun()
                    except psycopg.errors.UniqueViolation:
                        st.error("此技能項目已存在。")
        with connect() as con:
            df = query_df("SELECT skill_name AS 技能名稱,skill_category AS 技能類別,description AS 技能說明 FROM skill_catalog WHERE active=1 ORDER BY skill_category,skill_name", con)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if can_manage_modules():
            with connect() as con:
                editable_skills = con.execute("SELECT id,skill_name,skill_category,description FROM skill_catalog WHERE active=1 ORDER BY skill_category,skill_name").fetchall()
            if editable_skills:
                st.divider()
                st.subheader("修改／停用技能項目")
                skill_map = {f"{r['skill_name']}（{r['skill_category'] or '未分類'}）": r for r in editable_skills}
                selected_skill_label = st.selectbox("選擇技能項目", list(skill_map), key="edit_skill_catalog_select")
                selected_skill = skill_map[selected_skill_label]
                with st.form("edit_skill_catalog_form"):
                    edit_skill_name = st.text_input("技能名稱 *", value=selected_skill["skill_name"])
                    edit_skill_category = st.text_input("技能類別", value=selected_skill["skill_category"] or "")
                    edit_skill_description = st.text_area("技能說明", value=selected_skill["description"] or "")
                    update_skill = st.form_submit_button("儲存技能修改")
                if update_skill:
                    if not edit_skill_name.strip():
                        st.error("技能名稱為必填。")
                    else:
                        try:
                            with connect() as con:
                                old_skill_name = selected_skill["skill_name"]
                                # Update existing references as well; transaction rolls back if a unique conflict exists.
                                con.execute("UPDATE skill_catalog SET skill_name=%s,skill_category=%s,description=%s WHERE id=%s",
                                    (edit_skill_name.strip(),edit_skill_category.strip(),edit_skill_description.strip(),selected_skill["id"]))
                                if old_skill_name != edit_skill_name.strip():
                                    con.execute("UPDATE personnel_skill_records SET skill_name=%s,updated_at=%s WHERE skill_name=%s",
                                        (edit_skill_name.strip(),now_str(),old_skill_name))
                                    con.execute("UPDATE personnel_exam_records SET skill_name=%s WHERE skill_name=%s",
                                        (edit_skill_name.strip(),old_skill_name))
                                con.commit()
                            log_action(user["username"], "修改技能項目", f"{old_skill_name} -> {edit_skill_name.strip()}")
                            st.success("技能項目已更新。")
                            st.rerun()
                        except psycopg.errors.UniqueViolation:
                            st.error("技能名稱重複，或已有紀錄會造成重複技能，請先檢查相關資料。")
                confirm_deactivate_skill = st.checkbox("確認停用此技能（保留歷史技能／考試紀錄）", key="confirm_deactivate_skill")
                if st.button("停用技能項目", key="deactivate_skill_button"):
                    if not confirm_deactivate_skill:
                        st.error("請先勾選確認框。")
                    else:
                        with connect() as con:
                            con.execute("UPDATE skill_catalog SET active=0 WHERE id=%s", (selected_skill["id"],))
                            con.commit()
                        log_action(user["username"], "停用技能項目", selected_skill["skill_name"])
                        st.success("技能已停用；歷史紀錄保留。")
                        st.rerun()

    elif page == "人員技能矩陣":
        st.title("人員技能矩陣")
        show_module_permission_note()
        with connect() as con:
            people = con.execute("SELECT employee_code,full_name FROM personnel_profiles ORDER BY employee_code").fetchall()
            skills_catalog = con.execute("SELECT skill_name FROM skill_catalog WHERE active=1 ORDER BY skill_name").fetchall()
        if can_manage_modules() and people and skills_catalog:
            people_map = {f"{r['employee_code']} | {r['full_name']}": r["employee_code"] for r in people}
            skill_names = [r["skill_name"] for r in skills_catalog]
            with st.form("person_skill_form"):
                person_choice = st.selectbox("選擇人員", list(people_map))
                skill_choice = st.selectbox("技能項目", skill_names)
                level = st.selectbox("技能等級", ["待評估","初級 (1-2)","中級 (3-5)","熟練 (6-8)","專家 (9-10)"])
                assessed_date = st.date_input("評估日期")
                assessed_by = st.text_input("評估人員", value=user["display_name"])
                skill_notes = st.text_area("評估備註")
                save_skill_record = st.form_submit_button("儲存技能等級")
            if save_skill_record:
                code = people_map[person_choice]
                with connect() as con:
                    con.execute("""INSERT INTO personnel_skill_records(employee_code,skill_name,skill_level,assessed_date,assessed_by,notes,created_at,updated_at)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(employee_code,skill_name) DO UPDATE SET skill_level=excluded.skill_level,
                        assessed_date=excluded.assessed_date,assessed_by=excluded.assessed_by,notes=excluded.notes,updated_at=excluded.updated_at""",
                        (code,skill_choice,level,assessed_date.isoformat(),assessed_by.strip(),skill_notes.strip(),now_str(),now_str()))
                    con.commit()
                log_action(user["username"], "更新人員技能", f"{code} | {skill_choice} | {level}")
                st.success("人員技能等級已儲存。")
                st.rerun()
        elif not people:
            st.info("請先建立人員資料。")
        elif not skills_catalog:
            st.info("請先到「技能項目管理」建立技能項目。")
        with connect() as con:
            matrix = query_df("""SELECT p.employee_code AS 員工編號,p.full_name AS 姓名,p.department AS 部門,
                s.skill_name AS 技能項目,r.skill_level AS 技能等級,r.assessed_date AS 評估日期,r.assessed_by AS 評估人員,r.notes AS 備註
                FROM personnel_skill_records r JOIN personnel_profiles p ON p.employee_code=r.employee_code
                JOIN skill_catalog s ON s.skill_name=r.skill_name ORDER BY p.employee_code,s.skill_name""", con)
        st.dataframe(matrix, use_container_width=True, hide_index=True)
        if can_manage_modules():
            with connect() as con:
                skill_records = con.execute("""SELECT r.id,r.employee_code,p.full_name,r.skill_name,r.skill_level,r.assessed_date,r.assessed_by,r.notes
                    FROM personnel_skill_records r JOIN personnel_profiles p ON p.employee_code=r.employee_code
                    ORDER BY r.employee_code,r.skill_name""").fetchall()
                all_people = con.execute("SELECT employee_code,full_name FROM personnel_profiles ORDER BY employee_code").fetchall()
                all_skills = con.execute("SELECT skill_name FROM skill_catalog WHERE active=1 ORDER BY skill_name").fetchall()
            if skill_records:
                st.divider()
                st.subheader("修改／刪除技能評估紀錄")
                record_map = {f"{r['employee_code']} | {r['full_name']} | {r['skill_name']} | {r['skill_level']}": r for r in skill_records}
                selected_record_label = st.selectbox("選擇技能紀錄", list(record_map), key="edit_person_skill_record_select")
                selected_record = record_map[selected_record_label]
                people_map2 = {f"{r['employee_code']} | {r['full_name']}": r['employee_code'] for r in all_people}
                person_labels2 = list(people_map2)
                current_person_label = next((k for k,v in people_map2.items() if v == selected_record['employee_code']), person_labels2[0] if person_labels2 else None)
                skills2 = [r['skill_name'] for r in all_skills]
                if selected_record['skill_name'] not in skills2:
                    skills2.append(selected_record['skill_name'])
                levels2 = ["待評估","初級 (1-2)","中級 (3-5)","熟練 (6-8)","專家 (9-10)"]
                with st.form("edit_person_skill_record_form"):
                    edit_record_person = st.selectbox("人員", person_labels2, index=person_labels2.index(current_person_label) if current_person_label in person_labels2 else 0)
                    edit_record_skill = st.selectbox("技能項目", skills2, index=skills2.index(selected_record['skill_name']) if selected_record['skill_name'] in skills2 else 0)
                    edit_record_level = st.selectbox("技能等級", levels2, index=levels2.index(selected_record['skill_level']) if selected_record['skill_level'] in levels2 else 0)
                    edit_assessed_date = st.text_input("評估日期（YYYY-MM-DD）", value=selected_record['assessed_date'] or "")
                    edit_assessed_by = st.text_input("評估人員", value=selected_record['assessed_by'] or "")
                    edit_skill_notes = st.text_area("評估備註", value=selected_record['notes'] or "")
                    update_skill_record = st.form_submit_button("儲存技能紀錄修改")
                if update_skill_record:
                    if edit_assessed_date.strip() and (len(edit_assessed_date.strip()) != 10 or edit_assessed_date.strip()[4:5] != "-" or edit_assessed_date.strip()[7:8] != "-"):
                        st.error("評估日期請使用 YYYY-MM-DD 格式，或留空。")
                    else:
                        try:
                            with connect() as con:
                                con.execute("""UPDATE personnel_skill_records SET employee_code=%s,skill_name=%s,skill_level=%s,assessed_date=%s,assessed_by=%s,notes=%s,updated_at=%s WHERE id=%s""",
                                    (people_map2[edit_record_person],edit_record_skill,edit_record_level,edit_assessed_date.strip(),edit_assessed_by.strip(),edit_skill_notes.strip(),now_str(),selected_record['id']))
                                con.commit()
                            log_action(user["username"], "修改人員技能紀錄", str(selected_record['id']))
                            st.success("技能評估紀錄已更新。")
                            st.rerun()
                        except psycopg.errors.UniqueViolation:
                            st.error("此人員已有相同技能紀錄，請選擇其他技能或人員。")
                confirm_delete_skill_record = st.checkbox("確認刪除此筆技能評估紀錄", key="confirm_delete_skill_record")
                if st.button("刪除技能評估紀錄", key="delete_skill_record_button"):
                    if not confirm_delete_skill_record:
                        st.error("請先勾選確認框。")
                    else:
                        with connect() as con:
                            con.execute("DELETE FROM personnel_skill_records WHERE id=%s", (selected_record['id'],))
                            con.commit()
                        log_action(user["username"], "刪除人員技能紀錄", str(selected_record['id']))
                        st.success("技能評估紀錄已刪除。")
                        st.rerun()

    elif page == "培訓紀錄":
        st.title("培訓紀錄")
        show_module_permission_note()
        with connect() as con:
            people = con.execute("SELECT employee_code,full_name FROM personnel_profiles ORDER BY employee_code").fetchall()
        if people and can_manage_modules():
            people_map = {f"{r['employee_code']} | {r['full_name']}": r["employee_code"] for r in people}
            with st.form("training_record_form"):
                person_choice = st.selectbox("選擇人員", list(people_map))
                training_date = st.date_input("培訓日期")
                training_topic = st.text_input("培訓主題")
                training_hours = st.number_input("培訓時數", min_value=0.0, step=0.5)
                training_result = st.text_area("培訓結果")
                trainer = st.text_input("講師／訓練人員")
                training_notes = st.text_area("備註")
                save_training = st.form_submit_button("新增培訓紀錄")
            if save_training:
                if not training_topic.strip():
                    st.error("請輸入培訓主題。")
                else:
                    code = people_map[person_choice]
                    with connect() as con:
                        con.execute("""INSERT INTO personnel_training_records(employee_code,training_date,training_topic,training_hours,result,trainer,notes,created_by,created_at)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (code,training_date.isoformat(),training_topic.strip(),training_hours,training_result.strip(),trainer.strip(),training_notes.strip(),user["username"],now_str()))
                        # Keep the legacy summary field updated for compatibility with earlier screens.
                        con.execute("UPDATE personnel_profiles SET training_records=CASE WHEN COALESCE(training_records,'')='' THEN %s ELSE training_records || chr(10) || %s END,updated_at=%s WHERE employee_code=%s",
                            (f"{training_date.isoformat()} | {training_topic.strip()} | {training_hours:g}h | {training_result.strip()}",
                             f"{training_date.isoformat()} | {training_topic.strip()} | {training_hours:g}h | {training_result.strip()}",
                             now_str(),code))
                        con.commit()
                    log_action(user["username"], "新增培訓紀錄", f"{code} | {training_topic.strip()}")
                    st.success("培訓紀錄已新增。")
                    st.rerun()
        elif not people:
            st.info("請先建立人員資料。")
        with connect() as con:
            df = query_df("""SELECT t.training_date AS 培訓日期,p.employee_code AS 員工編號,p.full_name AS 姓名,
                t.training_topic AS 培訓主題,t.training_hours AS 培訓時數,t.result AS 培訓結果,t.trainer AS 講師,t.notes AS 備註
                FROM personnel_training_records t JOIN personnel_profiles p ON p.employee_code=t.employee_code
                ORDER BY t.training_date DESC,t.id DESC""", con)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if can_manage_modules():
            with connect() as con:
                training_rows = con.execute("""SELECT t.id,t.employee_code,p.full_name,t.training_date,t.training_topic,t.training_hours,t.result,t.trainer,t.notes
                    FROM personnel_training_records t JOIN personnel_profiles p ON p.employee_code=t.employee_code
                    ORDER BY t.training_date DESC,t.id DESC""").fetchall()
                training_people = con.execute("SELECT employee_code,full_name FROM personnel_profiles ORDER BY employee_code").fetchall()
            if training_rows:
                st.divider()
                st.subheader("修改／刪除培訓紀錄")
                training_map = {f"#{r['id']} | {r['employee_code']} {r['full_name']} | {r['training_date']} | {r['training_topic']}": r for r in training_rows}
                selected_training_label = st.selectbox("選擇培訓紀錄", list(training_map), key="edit_training_record_select")
                selected_training = training_map[selected_training_label]
                training_people_map = {f"{r['employee_code']} | {r['full_name']}": r['employee_code'] for r in training_people}
                current_training_person = next((k for k,v in training_people_map.items() if v == selected_training['employee_code']), list(training_people_map)[0])
                with st.form("edit_training_record_form"):
                    edit_training_person = st.selectbox("人員", list(training_people_map), index=list(training_people_map).index(current_training_person))
                    edit_training_date = st.text_input("培訓日期（YYYY-MM-DD）", value=selected_training['training_date'] or "")
                    edit_training_topic = st.text_input("培訓主題 *", value=selected_training['training_topic'] or "")
                    edit_training_hours = st.number_input("培訓時數", min_value=0.0, value=float(selected_training['training_hours'] or 0), step=0.5)
                    edit_training_result = st.text_area("培訓結果", value=selected_training['result'] or "")
                    edit_trainer = st.text_input("講師／訓練人員", value=selected_training['trainer'] or "")
                    edit_training_notes = st.text_area("備註", value=selected_training['notes'] or "")
                    update_training = st.form_submit_button("儲存培訓紀錄修改")
                if update_training:
                    if not edit_training_topic.strip() or len(edit_training_date.strip()) != 10 or edit_training_date.strip()[4:5] != "-" or edit_training_date.strip()[7:8] != "-":
                        st.error("請填寫培訓主題，日期格式須為 YYYY-MM-DD。")
                    else:
                        new_code = training_people_map[edit_training_person]
                        with connect() as con:
                            con.execute("""UPDATE personnel_training_records SET employee_code=%s,training_date=%s,training_topic=%s,training_hours=%s,result=%s,trainer=%s,notes=%s WHERE id=%s""",
                                (new_code,edit_training_date.strip(),edit_training_topic.strip(),edit_training_hours,edit_training_result.strip(),edit_trainer.strip(),edit_training_notes.strip(),selected_training['id']))
                            affected_codes = {selected_training['employee_code'], new_code}
                            for affected_code in affected_codes:
                                con.execute("""UPDATE personnel_profiles p SET training_records=COALESCE((SELECT string_agg(t.training_date || ' | ' || t.training_topic || ' | ' || t.training_hours::text || 'h | ' || COALESCE(t.result,''), chr(10) ORDER BY t.training_date,t.id) FROM personnel_training_records t WHERE t.employee_code=p.employee_code),'') ,updated_at=%s WHERE employee_code=%s""", (now_str(),affected_code))
                            con.commit()
                        log_action(user["username"], "修改培訓紀錄", str(selected_training['id']))
                        st.success("培訓紀錄已更新。")
                        st.rerun()
                confirm_delete_training = st.checkbox("確認刪除此筆培訓紀錄", key="confirm_delete_training_record")
                if st.button("刪除培訓紀錄", key="delete_training_record_button"):
                    if not confirm_delete_training:
                        st.error("請先勾選確認框。")
                    else:
                        affected_code = selected_training['employee_code']
                        with connect() as con:
                            con.execute("DELETE FROM personnel_training_records WHERE id=%s", (selected_training['id'],))
                            con.execute("""UPDATE personnel_profiles p SET training_records=COALESCE((SELECT string_agg(t.training_date || ' | ' || t.training_topic || ' | ' || t.training_hours::text || 'h | ' || COALESCE(t.result,''), chr(10) ORDER BY t.training_date,t.id) FROM personnel_training_records t WHERE t.employee_code=p.employee_code),'') ,updated_at=%s WHERE employee_code=%s""", (now_str(),affected_code))
                            con.commit()
                        log_action(user["username"], "刪除培訓紀錄", str(selected_training['id']))
                        st.success("培訓紀錄已刪除，培訓摘要已同步更新。")
                        st.rerun()

    elif page == "考試紀錄":
        st.title("考試紀錄")
        show_module_permission_note()
        with connect() as con:
            people = con.execute("SELECT employee_code,full_name FROM personnel_profiles ORDER BY employee_code").fetchall()
            skill_names = [r["skill_name"] for r in con.execute("SELECT skill_name FROM skill_catalog WHERE active=1 ORDER BY skill_name").fetchall()]
        if people and can_manage_modules():
            people_map = {f"{r['employee_code']} | {r['full_name']}": r["employee_code"] for r in people}
            with st.form("personnel_exam_form"):
                person_choice = st.selectbox("選擇人員", list(people_map))
                exam_date = st.date_input("考試日期")
                exam_name = st.text_input("考試名稱／項目")
                skill_name = st.selectbox("相關技能", ["（不指定）"] + skill_names)
                score = st.number_input("考試分數", min_value=0.0, value=0.0, step=1.0)
                max_score = st.number_input("滿分", min_value=1.0, value=100.0, step=1.0)
                passed = st.selectbox("考試結果", ["待判定","通過","未通過"])
                examiner = st.text_input("考官／評核人員", value=user["display_name"])
                exam_notes = st.text_area("備註")
                save_exam = st.form_submit_button("新增考試紀錄")
            if save_exam:
                if not exam_name.strip():
                    st.error("請輸入考試名稱／項目。")
                elif score > max_score:
                    st.error("考試分數不能大於滿分。")
                else:
                    code = people_map[person_choice]
                    with connect() as con:
                        con.execute("""INSERT INTO personnel_exam_records(employee_code,exam_date,exam_name,skill_name,score,max_score,passed,examiner,notes,created_by,created_at)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (code,exam_date.isoformat(),exam_name.strip(),"" if skill_name=="（不指定）" else skill_name,score,max_score,passed,examiner.strip(),exam_notes.strip(),user["username"],now_str()))
                        con.commit()
                    log_action(user["username"], "新增考試紀錄", f"{code} | {exam_name.strip()} | {score:g}/{max_score:g}")
                    st.success("考試紀錄已新增。")
                    st.rerun()
        elif not people:
            st.info("請先建立人員資料。")
        with connect() as con:
            df = query_df("""SELECT e.exam_date AS 考試日期,p.employee_code AS 員工編號,p.full_name AS 姓名,
                e.exam_name AS 考試項目,e.skill_name AS 相關技能,e.score AS 分數,e.max_score AS 滿分,
                e.passed AS 考試結果,e.examiner AS 考官,e.notes AS 備註
                FROM personnel_exam_records e JOIN personnel_profiles p ON p.employee_code=e.employee_code
                ORDER BY e.exam_date DESC,e.id DESC""", con)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if can_manage_modules():
            with connect() as con:
                exam_rows = con.execute("""SELECT e.id,e.employee_code,p.full_name,e.exam_date,e.exam_name,e.skill_name,e.score,e.max_score,e.passed,e.examiner,e.notes
                    FROM personnel_exam_records e JOIN personnel_profiles p ON p.employee_code=e.employee_code
                    ORDER BY e.exam_date DESC,e.id DESC""").fetchall()
                exam_people = con.execute("SELECT employee_code,full_name FROM personnel_profiles ORDER BY employee_code").fetchall()
                active_exam_skills = [r['skill_name'] for r in con.execute("SELECT skill_name FROM skill_catalog WHERE active=1 ORDER BY skill_name").fetchall()]
            if exam_rows:
                st.divider()
                st.subheader("修改／刪除考試紀錄")
                exam_map = {f"#{r['id']} | {r['employee_code']} {r['full_name']} | {r['exam_date']} | {r['exam_name']}": r for r in exam_rows}
                selected_exam_label = st.selectbox("選擇考試紀錄", list(exam_map), key="edit_exam_record_select")
                selected_exam = exam_map[selected_exam_label]
                exam_people_map = {f"{r['employee_code']} | {r['full_name']}": r['employee_code'] for r in exam_people}
                current_exam_person = next((k for k,v in exam_people_map.items() if v == selected_exam['employee_code']), list(exam_people_map)[0])
                exam_skills = ["（不指定）"] + active_exam_skills
                if selected_exam['skill_name'] and selected_exam['skill_name'] not in exam_skills:
                    exam_skills.append(selected_exam['skill_name'])
                selected_exam_skill = selected_exam['skill_name'] or "（不指定）"
                with st.form("edit_exam_record_form"):
                    edit_exam_person = st.selectbox("人員", list(exam_people_map), index=list(exam_people_map).index(current_exam_person))
                    edit_exam_date = st.text_input("考試日期（YYYY-MM-DD）", value=selected_exam['exam_date'] or "")
                    edit_exam_name = st.text_input("考試名稱／項目 *", value=selected_exam['exam_name'] or "")
                    edit_exam_skill = st.selectbox("相關技能", exam_skills, index=exam_skills.index(selected_exam_skill) if selected_exam_skill in exam_skills else 0)
                    edit_exam_score = st.number_input("考試分數", min_value=0.0, value=float(selected_exam['score'] or 0), step=1.0)
                    edit_exam_max_score = st.number_input("滿分", min_value=1.0, value=float(selected_exam['max_score'] or 100), step=1.0)
                    exam_results = ["待判定","通過","未通過"]
                    edit_exam_passed = st.selectbox("考試結果", exam_results, index=exam_results.index(selected_exam['passed']) if selected_exam['passed'] in exam_results else 0)
                    edit_examiner = st.text_input("考官／評核人員", value=selected_exam['examiner'] or "")
                    edit_exam_notes = st.text_area("備註", value=selected_exam['notes'] or "")
                    update_exam = st.form_submit_button("儲存考試紀錄修改")
                if update_exam:
                    if not edit_exam_name.strip() or len(edit_exam_date.strip()) != 10 or edit_exam_date.strip()[4:5] != "-" or edit_exam_date.strip()[7:8] != "-":
                        st.error("請填寫考試名稱，日期格式須為 YYYY-MM-DD。")
                    elif edit_exam_score > edit_exam_max_score:
                        st.error("考試分數不能大於滿分。")
                    else:
                        with connect() as con:
                            con.execute("""UPDATE personnel_exam_records SET employee_code=%s,exam_date=%s,exam_name=%s,skill_name=%s,score=%s,max_score=%s,passed=%s,examiner=%s,notes=%s WHERE id=%s""",
                                (exam_people_map[edit_exam_person],edit_exam_date.strip(),edit_exam_name.strip(),"" if edit_exam_skill=="（不指定）" else edit_exam_skill,edit_exam_score,edit_exam_max_score,edit_exam_passed,edit_examiner.strip(),edit_exam_notes.strip(),selected_exam['id']))
                            con.commit()
                        log_action(user["username"], "修改考試紀錄", str(selected_exam['id']))
                        st.success("考試紀錄已更新。")
                        st.rerun()
                confirm_delete_exam = st.checkbox("確認刪除此筆考試紀錄", key="confirm_delete_exam_record")
                if st.button("刪除考試紀錄", key="delete_exam_record_button"):
                    if not confirm_delete_exam:
                        st.error("請先勾選確認框。")
                    else:
                        with connect() as con:
                            con.execute("DELETE FROM personnel_exam_records WHERE id=%s", (selected_exam['id'],))
                            con.commit()
                        log_action(user["username"], "刪除考試紀錄", str(selected_exam['id']))
                        st.success("考試紀錄已刪除。")
                        st.rerun()

    elif page == "設備總覽":
        st.title("設備管理模塊")
        show_module_permission_note()
        today = date.today().isoformat()
        from datetime import timedelta
        due_soon_date = (date.today() + timedelta(days=7)).isoformat()
        with connect() as con:
            equipment_count = con.execute("SELECT COUNT(*) AS n FROM equipment").fetchone()["n"]
            abnormal_open = con.execute("SELECT COUNT(*) AS n FROM equipment_abnormalities WHERE status!='已結案'").fetchone()["n"]
            due_count = con.execute("SELECT COUNT(*) AS n FROM equipment WHERE COALESCE(next_maintenance_date,'')<>'' AND next_maintenance_date<=%s", (today,)).fetchone()["n"]
            equipment_df = query_df("""
                SELECT
                    e.equipment_code AS 設備編號,
                    e.equipment_name AS 設備名稱,
                    e.location AS 位置,
                    e.department AS 負責部門,
                    e.status AS 設備狀態,
                    e.last_maintenance_date AS 上次保養日期,
                    e.next_maintenance_date AS 下次保養日期,
                    CASE
                        WHEN COALESCE(e.next_maintenance_date,'')='' THEN '⚪ 未設定保養日期'
                        WHEN e.next_maintenance_date<=%s THEN '🔴 待保養／已逾期'
                        WHEN e.next_maintenance_date<=%s THEN '🟡 7 天內到期'
                        ELSE '🟢 保養日期正常'
                    END AS 保養提醒,
                    CASE
                        WHEN COALESCE(a.open_count,0)>0 THEN '🔴 未結案異常 (' || a.open_count::text || ')'
                        ELSE '🟢 無未結案異常'
                    END AS 異常提醒
                FROM equipment e
                LEFT JOIN (
                    SELECT equipment_id, COUNT(*) AS open_count
                    FROM equipment_abnormalities
                    WHERE status!='已結案'
                    GROUP BY equipment_id
                ) a ON a.equipment_id=e.id
                ORDER BY
                    CASE WHEN COALESCE(e.next_maintenance_date,'')<>'' AND e.next_maintenance_date<=%s THEN 0
                         WHEN COALESCE(a.open_count,0)>0 THEN 1
                         WHEN COALESCE(e.next_maintenance_date,'')<>'' AND e.next_maintenance_date<=%s THEN 2
                         ELSE 3 END,
                    e.equipment_code
            """, con, params=(today, due_soon_date, today, due_soon_date))
        a,b,c = st.columns(3)
        a.metric("設備數量", equipment_count)
        b.metric("🔴 待保養設備", due_count)
        c.metric("🔴 未結案異常", abnormal_open)
        st.caption("狀態標示：🔴 已到保養日或逾期／有未結案異常；🟡 7 天內到期；🟢 正常；⚪ 尚未設定保養日期。異常數量會顯示在設備所屬列。")
        st.subheader("設備維修與異常概況")
        if not equipment_df.empty:
            st.dataframe(equipment_df, use_container_width=True, hide_index=True)
        else:
            st.info("目前尚無設備資料。")

    elif page == "設備資料管理":
        st.title("設備資料管理")
        show_module_permission_note()
        if user["role"] in ("system_admin", "manager", "employee"):
            with st.form("equipment_form"):
                a,b = st.columns(2)
                equipment_code = a.text_input("設備編號 *")
                equipment_name = b.text_input("設備名稱 *")
                c,d = st.columns(2)
                model = c.text_input("型號")
                location = d.text_input("位置")
                e,f = st.columns(2)
                department = e.text_input("負責部門", value="技術機械部")
                owner = f.text_input("設備負責人")
                g,h = st.columns(2)
                install_date = g.date_input("安裝日期", value=None)
                status = h.selectbox("設備狀態", ["正常","維修中","停用"])
                interval = st.number_input("保養週期（天）", min_value=1, value=30, step=1)
                last_date = st.date_input("上次保養日期", value=None, key="equipment_last_date")
                notes = st.text_area("備註", key="equipment_notes")
                save_equipment = st.form_submit_button("新增設備")
            if save_equipment:
                if not equipment_code.strip() or not equipment_name.strip():
                    st.error("設備編號與設備名稱為必填。")
                else:
                    next_date = ""
                    if last_date:
                        from datetime import timedelta
                        next_date = (last_date + timedelta(days=int(interval))).isoformat()
                    try:
                        with connect() as con:
                            con.execute("""INSERT INTO equipment(equipment_code,equipment_name,model,location,department,owner,install_date,status,maintenance_interval_days,last_maintenance_date,next_maintenance_date,notes,created_at,updated_at)
                                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (equipment_code.strip(),equipment_name.strip(),model.strip(),location.strip(),department.strip(),owner.strip(),
                                 install_date.isoformat() if install_date else "",status,int(interval),last_date.isoformat() if last_date else "",next_date,
                                 notes.strip(),now_str(),now_str()))
                            con.commit()
                        log_action(user["username"], "新增設備", equipment_code.strip())
                        st.success("設備資料已儲存。")
                        st.rerun()
                    except psycopg.errors.UniqueViolation:
                        st.error("設備編號已存在。")
        else:
            st.info("目前為檢視權限；新增或修改設備資料需管理員權限。")
        with connect() as con:
            equipment_rows = con.execute("SELECT * FROM equipment ORDER BY equipment_code").fetchall()
        if equipment_rows and user["role"] in ("system_admin", "manager"):
            st.subheader("修改／刪除設備")
            equipment_map = {f"{r['equipment_code']} | {r['equipment_name']} (ID:{r['id']})": dict(r) for r in equipment_rows}
            selected_equipment_label = st.selectbox("選擇要修改的設備", list(equipment_map), key="edit_equipment_select")
            selected_equipment = equipment_map[selected_equipment_label]
            with st.form("edit_equipment_form"):
                a,b = st.columns(2)
                edit_equipment_code = a.text_input("設備編號 *", value=selected_equipment["equipment_code"] or "")
                edit_equipment_name = b.text_input("設備名稱 *", value=selected_equipment["equipment_name"] or "")
                c,d = st.columns(2)
                edit_model = c.text_input("型號", value=selected_equipment["model"] or "")
                edit_location = d.text_input("位置", value=selected_equipment["location"] or "")
                e,f = st.columns(2)
                edit_department = e.text_input("負責部門", value=selected_equipment["department"] or "")
                edit_owner = f.text_input("設備負責人", value=selected_equipment["owner"] or "")
                g,h = st.columns(2)
                edit_install_date = g.text_input("安裝日期（YYYY-MM-DD，可空白）", value=selected_equipment["install_date"] or "")
                statuses = ["正常", "維修中", "停用"]
                old_status = selected_equipment["status"] or "正常"
                edit_status = h.selectbox("設備狀態", statuses, index=statuses.index(old_status) if old_status in statuses else 0)
                edit_interval = st.number_input("保養週期（天）", min_value=1, value=int(selected_equipment["maintenance_interval_days"] or 30), step=1, key="edit_equipment_interval")
                edit_last_date = st.text_input("上次保養日期（YYYY-MM-DD，可空白）", value=selected_equipment["last_maintenance_date"] or "")
                edit_next_date = st.text_input("下次保養日期（YYYY-MM-DD，可空白）", value=selected_equipment["next_maintenance_date"] or "")
                edit_notes = st.text_area("備註", value=selected_equipment["notes"] or "", key="edit_equipment_notes")
                save_equipment_changes = st.form_submit_button("儲存設備修改")
            if save_equipment_changes:
                from datetime import datetime as _dt
                date_values = [edit_install_date.strip(), edit_last_date.strip(), edit_next_date.strip()]
                try:
                    for date_value in date_values:
                        if date_value:
                            _dt.strptime(date_value, "%Y-%m-%d")
                    if not edit_equipment_code.strip() or not edit_equipment_name.strip():
                        st.error("設備編號與設備名稱為必填。")
                    else:
                        with connect() as con:
                            con.execute("""UPDATE equipment SET equipment_code=%s,equipment_name=%s,model=%s,location=%s,department=%s,owner=%s,install_date=%s,status=%s,maintenance_interval_days=%s,last_maintenance_date=%s,next_maintenance_date=%s,notes=%s,updated_at=%s WHERE id=%s""",
                                (edit_equipment_code.strip(),edit_equipment_name.strip(),edit_model.strip(),edit_location.strip(),edit_department.strip(),edit_owner.strip(),edit_install_date.strip(),edit_status,int(edit_interval),edit_last_date.strip(),edit_next_date.strip(),edit_notes.strip(),now_str(),selected_equipment["id"]))
                            con.commit()
                        log_action(user["username"], "修改設備", f"{selected_equipment['equipment_code']} -> {edit_equipment_code.strip()}")
                        st.success("設備資料已修改。")
                        st.rerun()
                except ValueError:
                    st.error("日期格式錯誤，請使用 YYYY-MM-DD。")
                except psycopg.errors.UniqueViolation:
                    st.error("設備編號已被其他設備使用。")
            st.checkbox("我確認要刪除所選設備；若有保養或異常紀錄將禁止刪除", key="confirm_delete_equipment")
            if st.button("刪除所選設備", key="delete_equipment_button"):
                if not st.session_state.get("confirm_delete_equipment", False):
                    st.error("請先勾選刪除確認框。")
                else:
                    with connect() as con:
                        related = con.execute("SELECT (SELECT COUNT(*) FROM maintenance_records WHERE equipment_id=%s) + (SELECT COUNT(*) FROM equipment_abnormalities WHERE equipment_id=%s) AS n", (selected_equipment["id"], selected_equipment["id"])).fetchone()["n"]
                        if related:
                            st.error(f"此設備已有 {related} 筆保養／異常紀錄，為保留歷史資料，不能直接刪除。請先將設備狀態改為「停用」。")
                        else:
                            con.execute("DELETE FROM equipment WHERE id=%s", (selected_equipment["id"],))
                            con.commit()
                            log_action(user["username"], "刪除設備", selected_equipment["equipment_code"])
                            st.success("設備已刪除。")
                            st.rerun()
        with connect() as con:
            df = query_df("SELECT equipment_code AS 設備編號,equipment_name AS 設備名稱,model AS 型號,location AS 位置,department AS 負責部門,owner AS 設備負責人,install_date AS 安裝日期,status AS 設備狀態,maintenance_interval_days AS 保養週期天數,last_maintenance_date AS 上次保養日期,next_maintenance_date AS 下次保養日期,notes AS 備註 FROM equipment ORDER BY equipment_code", con)
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif page == "保養計畫與紀錄":
        st.title("保養計畫與紀錄")
        show_module_permission_note()
        with connect() as con:
            eqs = con.execute("SELECT id,equipment_code,equipment_name,maintenance_interval_days FROM equipment ORDER BY equipment_code").fetchall()
        if eqs and user["role"] in ("system_admin", "manager", "employee"):
            eqmap = {f"{r['equipment_code']} | {r['equipment_name']}": dict(r) for r in eqs}
            with st.form("maintenance_form"):
                eq_choice = st.selectbox("選擇設備", list(eqmap))
                maintenance_date = st.date_input("保養日期")
                maintenance_type = st.selectbox("保養類型", ["定期保養","故障維修","點檢"])
                technician = st.text_input("維修技術員", value=user["display_name"])
                duration = st.number_input("維修時數", min_value=0.0, step=0.5)
                result = st.text_area("保養結果")
                parts_used = st.text_area("使用備品")
                next_date = st.date_input("下次保養日期（可留空自動計算）", value=None)
                notes = st.text_area("備註", key="maintenance_notes")
                save_maintenance = st.form_submit_button("新增保養紀錄")
            if save_maintenance:
                equipment = eqmap[eq_choice]
                if not next_date:
                    from datetime import timedelta
                    next_date = maintenance_date + timedelta(days=int(equipment["maintenance_interval_days"]))
                with connect() as con:
                    con.execute("""INSERT INTO maintenance_records(equipment_id,maintenance_date,maintenance_type,technician,duration_hours,result,parts_used,next_maintenance_date,notes,created_by,created_at)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (equipment["id"],maintenance_date.isoformat(),maintenance_type,technician.strip(),duration,result.strip(),parts_used.strip(),next_date.isoformat() if next_date else "",notes.strip(),user["username"],now_str()))
                    con.execute("UPDATE equipment SET last_maintenance_date=%s,next_maintenance_date=%s,status='正常',updated_at=%s WHERE id=%s",
                                (maintenance_date.isoformat(),next_date.isoformat() if next_date else "",now_str(),equipment["id"]))
                    con.commit()
                log_action(user["username"], "新增保養紀錄", f"{equipment['equipment_code']} | {maintenance_type}")
                st.success("保養紀錄已新增。")
                st.rerun()
        elif not eqs:
            st.info("請先建立設備資料。")
        with connect() as con:
            maintenance_rows = con.execute("SELECT m.*,e.equipment_code,e.equipment_name FROM maintenance_records m JOIN equipment e ON e.id=m.equipment_id ORDER BY m.maintenance_date DESC,m.id DESC").fetchall()
            eqs_all = con.execute("SELECT id,equipment_code,equipment_name FROM equipment ORDER BY equipment_code").fetchall()
        if maintenance_rows and user["role"] in ("system_admin", "manager"):
            st.subheader("修改／刪除保養紀錄")
            maint_map = {f"{r['maintenance_date']} | {r['equipment_code']} | {r['maintenance_type']} | ID:{r['id']}": dict(r) for r in maintenance_rows}
            maint_label = st.selectbox("選擇保養紀錄", list(maint_map), key="edit_maintenance_select")
            mr = maint_map[maint_label]
            eq_label_map = {f"{r['equipment_code']} | {r['equipment_name']}": r['id'] for r in eqs_all}
            current_eq_label = next((k for k,v in eq_label_map.items() if v == mr['equipment_id']), list(eq_label_map)[0])
            with st.form("edit_maintenance_form"):
                m_eq = st.selectbox("設備", list(eq_label_map), index=list(eq_label_map).index(current_eq_label))
                m_date = st.text_input("保養日期（YYYY-MM-DD）", value=mr['maintenance_date'] or "")
                m_type = st.selectbox("保養類型", ["定期保養","故障維修","點檢"], index=["定期保養","故障維修","點檢"].index(mr['maintenance_type']) if mr['maintenance_type'] in ["定期保養","故障維修","點檢"] else 0)
                m_technician = st.text_input("維修技術員", value=mr['technician'] or "")
                m_duration = st.number_input("維修時數", min_value=0.0, value=float(mr['duration_hours'] or 0), step=0.5)
                m_result = st.text_area("保養結果", value=mr['result'] or "")
                m_parts = st.text_area("使用備品", value=mr['parts_used'] or "")
                m_next = st.text_input("下次保養日期（YYYY-MM-DD，可空白）", value=mr['next_maintenance_date'] or "")
                m_notes = st.text_area("備註", value=mr['notes'] or "")
                save_m_changes = st.form_submit_button("儲存保養紀錄修改")
            if save_m_changes:
                from datetime import datetime as _dt
                try:
                    _dt.strptime(m_date.strip(), "%Y-%m-%d")
                    if m_next.strip(): _dt.strptime(m_next.strip(), "%Y-%m-%d")
                    with connect() as con:
                        con.execute("UPDATE maintenance_records SET equipment_id=%s,maintenance_date=%s,maintenance_type=%s,technician=%s,duration_hours=%s,result=%s,parts_used=%s,next_maintenance_date=%s,notes=%s WHERE id=%s", (eq_label_map[m_eq],m_date.strip(),m_type,m_technician.strip(),m_duration,m_result.strip(),m_parts.strip(),m_next.strip(),m_notes.strip(),mr['id']))
                        con.commit()
                    log_action(user["username"], "修改保養紀錄", str(mr['id']))
                    st.success("保養紀錄已修改。")
                    st.rerun()
                except ValueError:
                    st.error("日期格式錯誤，請使用 YYYY-MM-DD。")
            st.checkbox("確認刪除此筆保養紀錄", key="confirm_delete_maintenance")
            if st.button("刪除保養紀錄", key="delete_maintenance_button"):
                if not st.session_state.get("confirm_delete_maintenance", False): st.error("請先勾選確認框。")
                else:
                    with connect() as con:
                        con.execute("DELETE FROM maintenance_records WHERE id=%s", (mr['id'],))
                        con.commit()
                    log_action(user["username"], "刪除保養紀錄", str(mr['id']))
                    st.success("保養紀錄已刪除。設備台帳的保養日期未自動清除，請依實際最新保養狀況確認。")
                    st.rerun()
        with connect() as con:
            df = query_df("""SELECT e.equipment_code AS 設備編號,e.equipment_name AS 設備名稱,m.maintenance_date AS 保養日期,m.maintenance_type AS 保養類型,m.technician AS 維修技術員,m.duration_hours AS 維修時數,m.result AS 保養結果,m.parts_used AS 使用備品,m.next_maintenance_date AS 下次保養日期,m.notes AS 備註 FROM maintenance_records m JOIN equipment e ON e.id=m.equipment_id ORDER BY m.maintenance_date DESC,m.id DESC""", con)
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif page == "設備異常紀錄":
        st.title("設備異常紀錄")
        show_module_permission_note()
        with connect() as con:
            eqs = con.execute("SELECT id,equipment_code,equipment_name FROM equipment ORDER BY equipment_code").fetchall()
        if eqs and user["role"] in ("system_admin", "manager", "employee"):
            eqmap = {f"{r['equipment_code']} | {r['equipment_name']}": r["id"] for r in eqs}
            with st.form("abnormality_form"):
                eq_choice = st.selectbox("選擇設備", list(eqmap))
                occurred_at = st.text_input("異常發生時間（YYYY-MM-DD HH:MM:SS）", value=now_str())
                severity = st.selectbox("異常嚴重程度", ["一般","重大","緊急"])
                symptom = st.text_area("異常現象 *")
                root_cause = st.text_area("異常原因／根本原因")
                action_taken = st.text_area("處理措施與結果")
                handler_name = st.text_input("處理人員", value=user["display_name"])
                handling_started_at = st.text_input("開始處理時間（YYYY-MM-DD HH:MM:SS）", value=now_str())
                handling_finished_at = st.text_input("處理完成時間（未完成可留空）", value="")
                save_abnormal = st.form_submit_button("新增異常紀錄")
            if save_abnormal:
                if not symptom.strip():
                    st.error("請填寫異常現象。")
                elif not handler_name.strip():
                    st.error("請填寫處理人員。")
                else:
                    try:
                        from datetime import datetime as _dt
                        occurred_dt = _dt.strptime(occurred_at.strip(), "%Y-%m-%d %H:%M:%S")
                        started_dt = _dt.strptime(handling_started_at.strip(), "%Y-%m-%d %H:%M:%S")
                        finished_raw = handling_finished_at.strip()
                        finished_dt = _dt.strptime(finished_raw, "%Y-%m-%d %H:%M:%S") if finished_raw else None
                        if finished_dt and finished_dt < started_dt:
                            st.error("處理完成時間不可早於開始處理時間。")
                            raise ValueError("處理完成時間不可早於開始處理時間。")
                        handling_hours = round((finished_dt - started_dt).total_seconds()/3600, 2) if finished_dt else 0.0
                        with connect() as con:
                            con.execute("""INSERT INTO equipment_abnormalities(
                                equipment_id,occurred_at,severity,symptom,root_cause,action_taken,
                                downtime_hours,status,closed_at,reported_by,created_at,
                                handler_name,handling_started_at,handling_finished_at,handling_hours)
                                VALUES(%s,%s,%s,%s,%s,%s,0,'',%s,%s,%s,%s,%s,%s,%s)""",
                                (eqmap[eq_choice],occurred_dt.strftime("%Y-%m-%d %H:%M:%S"),severity,symptom.strip(),
                                 root_cause.strip(),action_taken.strip(),finished_raw,user["username"],now_str(),
                                 handler_name.strip(),started_dt.strftime("%Y-%m-%d %H:%M:%S"),finished_raw,handling_hours))
                            con.commit()
                        log_action(user["username"], "新增設備異常", f"{eq_choice} | {handler_name.strip()} | {symptom.strip()}")
                        st.success(f"設備異常已記錄。處理時數：{handling_hours:.2f} 小時。" if finished_dt else "設備異常已記錄；處理完成後可補登完成時間以計算處理時數。")
                        st.rerun()
                    except ValueError as e:
                        if "does not match format" in str(e) or "time data" in str(e):
                            st.error("時間格式錯誤，請使用 YYYY-MM-DD HH:MM:SS。")
                    except Exception as e:
                        st.error(f"儲存異常紀錄失敗：{e}")
        elif not eqs:
            st.info("請先建立設備資料。")
        with connect() as con:
            df = query_df("""SELECT e.equipment_code AS 設備編號,e.equipment_name AS 設備名稱,
                a.occurred_at AS 異常發生時間,a.severity AS 嚴重程度,a.symptom AS 異常現象,
                a.root_cause AS 異常原因,a.action_taken AS 處理措施與結果,a.handler_name AS 處理人員,
                a.handling_started_at AS 開始處理時間,a.handling_finished_at AS 處理完成時間,
                a.handling_hours AS 處理時數,a.reported_by AS 登錄帳號
                FROM equipment_abnormalities a JOIN equipment e ON e.id=a.equipment_id
                ORDER BY a.occurred_at DESC,a.id DESC""", con)
        st.dataframe(df, use_container_width=True, hide_index=True)
        with connect() as con:
            abnormal_rows = con.execute("SELECT a.*,e.equipment_code,e.equipment_name FROM equipment_abnormalities a JOIN equipment e ON e.id=a.equipment_id ORDER BY a.occurred_at DESC,a.id DESC").fetchall()
            abnormal_eqs = con.execute("SELECT id,equipment_code,equipment_name FROM equipment ORDER BY equipment_code").fetchall()
        if abnormal_rows and user["role"] in ("system_admin", "manager"):
            st.subheader("修改／刪除設備異常紀錄")
            abnormal_map = {f"{r['occurred_at']} | {r['equipment_code']} | {str(r['symptom'])[:35]} | ID:{r['id']}": dict(r) for r in abnormal_rows}
            abnormal_label = st.selectbox("選擇異常紀錄", list(abnormal_map), key="edit_abnormal_select")
            ar = abnormal_map[abnormal_label]
            abnormal_eq_map = {f"{r['equipment_code']} | {r['equipment_name']}": r['id'] for r in abnormal_eqs}
            current_ab_eq = next((k for k,v in abnormal_eq_map.items() if v == ar['equipment_id']), list(abnormal_eq_map)[0])
            with st.form("edit_abnormal_form"):
                ab_eq = st.selectbox("設備", list(abnormal_eq_map), index=list(abnormal_eq_map).index(current_ab_eq))
                ab_occurred = st.text_input("異常發生時間（YYYY-MM-DD HH:MM:SS）", value=ar['occurred_at'] or "")
                ab_severity = st.selectbox("嚴重程度", ["一般","重大","緊急"], index=["一般","重大","緊急"].index(ar['severity']) if ar['severity'] in ["一般","重大","緊急"] else 0)
                ab_symptom = st.text_area("異常現象 *", value=ar['symptom'] or "")
                ab_cause = st.text_area("異常原因／根本原因", value=ar['root_cause'] or "")
                ab_action = st.text_area("處理措施與結果", value=ar['action_taken'] or "")
                ab_handler = st.text_input("處理人員", value=ar['handler_name'] or "")
                ab_started = st.text_input("開始處理時間（YYYY-MM-DD HH:MM:SS）", value=ar['handling_started_at'] or "")
                ab_finished = st.text_input("完成時間（可空白）", value=ar['handling_finished_at'] or "")
                ab_status = st.selectbox("處理狀態", ["未結案","處理中","已結案"], index=["未結案","處理中","已結案"].index(ar['status']) if ar['status'] in ["未結案","處理中","已結案"] else 0)
                save_ab_changes = st.form_submit_button("儲存異常紀錄修改")
            if save_ab_changes:
                from datetime import datetime as _dt
                try:
                    occurred_dt = _dt.strptime(ab_occurred.strip(), "%Y-%m-%d %H:%M:%S")
                    started_dt = _dt.strptime(ab_started.strip(), "%Y-%m-%d %H:%M:%S")
                    finished_dt = _dt.strptime(ab_finished.strip(), "%Y-%m-%d %H:%M:%S") if ab_finished.strip() else None
                    if not ab_symptom.strip() or not ab_handler.strip():
                        st.error("異常現象與處理人員為必填。")
                    elif finished_dt and finished_dt < started_dt:
                        st.error("完成時間不可早於開始處理時間。")
                    else:
                        handling_hours = round((finished_dt-started_dt).total_seconds()/3600, 2) if finished_dt else 0.0
                        with connect() as con:
                            con.execute("UPDATE equipment_abnormalities SET equipment_id=%s,occurred_at=%s,severity=%s,symptom=%s,root_cause=%s,action_taken=%s,handler_name=%s,handling_started_at=%s,handling_finished_at=%s,handling_hours=%s,status=%s,closed_at=%s WHERE id=%s", (abnormal_eq_map[ab_eq],occurred_dt.strftime("%Y-%m-%d %H:%M:%S"),ab_severity,ab_symptom.strip(),ab_cause.strip(),ab_action.strip(),ab_handler.strip(),started_dt.strftime("%Y-%m-%d %H:%M:%S"),ab_finished.strip(),handling_hours,ab_status,ab_finished.strip() if ab_status=="已結案" else "",ar['id']))
                            con.commit()
                        log_action(user["username"], "修改設備異常", str(ar['id']))
                        st.success("設備異常紀錄已修改。")
                        st.rerun()
                except ValueError:
                    st.error("時間格式錯誤，請使用 YYYY-MM-DD HH:MM:SS。")
            st.checkbox("確認刪除此筆異常紀錄", key="confirm_delete_abnormal")
            if st.button("刪除異常紀錄", key="delete_abnormal_button"):
                if not st.session_state.get("confirm_delete_abnormal", False): st.error("請先勾選確認框。")
                else:
                    with connect() as con:
                        con.execute("DELETE FROM equipment_abnormalities WHERE id=%s", (ar['id'],))
                        con.commit()
                    log_action(user["username"], "刪除設備異常", str(ar['id']))
                    st.success("設備異常紀錄已刪除。")
                    st.rerun()
        st.subheader("人員處理異常時間分析")
        with connect() as con:
            analysis_df = query_df("""SELECT handler_name AS 處理人員,
                COUNT(*) AS 處理異常件數,
                ROUND(AVG(NULLIF(handling_hours,0))::numeric,2) AS 平均處理時數,
                ROUND(SUM(handling_hours)::numeric,2) AS 累計處理時數,
                ROUND(MAX(handling_hours)::numeric,2) AS 最長處理時數
                FROM equipment_abnormalities
                WHERE COALESCE(handler_name,'')<>'' GROUP BY handler_name ORDER BY 累計處理時數 DESC""", con)
        st.dataframe(analysis_df, use_container_width=True, hide_index=True)


    elif page == "總覽儀表板":
        st_autorefresh(
            interval=10_000,
            limit=None,
            key="dashboard_auto_refresh",
        )
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
            st.dataframe(view[["備品編號","備品名稱","規格","目前庫存","最低庫存","目標庫存","缺少數量"]].sort_values("目前庫存"), use_container_width=True, hide_index=True)
        else:
            st.success("目前沒有低於最低庫存的備品。")

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
        movement_types = ["出庫"] if user["role"] == "employee" else ["入庫", "出庫"]
        kind = st.radio("異動類型", movement_types, horizontal=True, key="movement_kind")
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
            if user["role"] == "employee":
                person = user["display_name"]
                st.text_input("領用人 / 相關人員", value=person, disabled=True)
            else:
                person = st.selectbox("領用人 / 相關人員", staff)
            if kind == "出庫":
                equipment_id = st.text_input("使用設備 *", value="", help="出庫時必填，請填寫實際使用的設備編號。")
                reference_no = ""
            else:
                equipment_id = ""
                reference_no = st.text_input("採購單 / 維修單 / 參考單號")
            note = st.text_area("備註")
            submit = st.form_submit_button("確認並登記異動", use_container_width=True)
        if submit:
            try:
                if user["role"] == "employee" and kind != "出庫":
                    st.error("員工權限只能登記出庫。")
                elif kind == "出庫" and not equipment_id.strip():
                    st.error("出庫時必須填寫使用設備編號。")
                elif reason_choice == "其他" and not custom_reason.strip():
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
        q = st.text_input("搜尋備品編號、名稱或規格")
        if q:
            # 先用完整資料搜尋，再只隱藏此頁面的指定顯示欄位；資料庫與其他模組不變。
            mask = df.astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)
            df = df[mask]
        hidden_columns = ["id", "儲位", "關聯設備編號"]
        display_df = df.drop(columns=hidden_columns, errors="ignore")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.download_button("下載目前庫存 CSV", display_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
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
        require_manager_or_higher()
        if user["role"] == "system_admin":
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
            c4,c5 = st.columns(2)
            category = c4.text_input("類別")
            unit = c5.text_input("單位", value="個")
            c6,c7,c8 = st.columns(3)
            min_stock = c6.number_input("最低庫存", min_value=0.0, step=1.0)
            target_stock = c7.number_input("目標庫存", min_value=0.0, step=1.0)
            cost = c8.number_input("單價", min_value=0.0, step=1.0)
            opening = st.number_input("期初庫存", min_value=0.0, step=1.0)
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
                            (code.strip(),name.strip(),spec.strip(),category.strip(),unit.strip() or "個","",
                             "",min_stock,target_stock,cost,opening,1,now_str(),now_str()))
                        con.commit()
                    log_action(user["username"], "新增備品", code.strip())
                    st.success("新增成功。")
                    st.rerun()
                except psycopg.IntegrityError:
                    st.error("備品編號已存在。")
        if user["role"] == "system_admin":
            st.markdown("#### 失效與恢復")
            with connect() as con:
                active_items = query_df("SELECT code AS 備品編號,name AS 備品名稱 FROM items WHERE active=1 ORDER BY code", con)
                inactive_items = query_df("SELECT code AS 備品編號,name AS 備品名稱 FROM items WHERE active=0 ORDER BY code", con)
            if not active_items.empty:
                active_labels = active_items.apply(lambda r:f"{r['備品編號']} | {r['備品名稱']}",axis=1).tolist()
                disable_choices = st.multiselect(
                    "選擇要失效的備品（可複選）", active_labels,
                    key="item_batch_disable_choices"
                )
                confirm_disable = st.checkbox(
                    "我已確認將所選備品批量設為失效；歷史異動紀錄會保留。",
                    key="confirm_item_batch_disable"
                )
                if st.button("確認批量失效", type="secondary", key="confirm_batch_disable_button"):
                    if not disable_choices:
                        st.warning("請至少選擇一筆備品。")
                    elif not confirm_disable:
                        st.error("請先勾選確認框。")
                    else:
                        codes = [label.split(" | ", 1)[0] for label in disable_choices]
                        changed = 0
                        with connect() as con:
                            with con.cursor() as cur:
                                cur.execute(
                                    "UPDATE items SET active=0,updated_at=%s WHERE active=1 AND code = ANY(%s)",
                                    (now_str(), codes)
                                )
                                changed = cur.rowcount
                            con.commit()
                        log_action(user["username"], "批量失效備品", f"共 {changed} 筆：" + ", ".join(codes))
                        st.success(f"已將 {changed} 筆備品設為失效；歷史異動紀錄保留。")
                        st.rerun()
            if not inactive_items.empty:
                restore_choice = st.selectbox("選擇要恢復的備品", inactive_items.apply(lambda r:f"{r['備品編號']} | {r['備品名稱']}",axis=1).tolist(), key="item_restore_choice")
                if st.button("確認恢復"):
                    code = restore_choice.split(" | ",1)[0]
                    with connect() as con:
                        con.execute("UPDATE items SET active=1,updated_at=%s WHERE code=%s AND active=0", (now_str(),code))
                        con.commit()
                    log_action(user["username"], "恢復備品", code)
                    st.success("備品已恢復啟用。")
                    st.rerun()
            st.markdown("#### 刪除失效料號")
            if not inactive_items.empty:
                delete_item = st.selectbox("選擇要永久刪除的失效料號", inactive_items.apply(lambda r:f"{r['備品編號']} | {r['備品名稱']}",axis=1).tolist(), key="item_delete_choice")
                confirm_item = st.checkbox("我已確認永久刪除此失效料號及其所有庫存異動紀錄（無法復原）", key="confirm_item_delete")
                if st.button("刪除料號", type="secondary"):
                    code = delete_item.split(" | ",1)[0]
                    if not confirm_item:
                        st.error("請先勾選確認框。")
                    else:
                        with connect() as con:
                            row = con.execute("SELECT id,active FROM items WHERE code=%s", (code,)).fetchone()
                            if not row or int(row["active"]) != 0:
                                st.error("只能刪除已失效的備品。")
                            else:
                                count = con.execute("SELECT COUNT(*) AS n FROM movements WHERE item_id=%s", (row["id"],)).fetchone()["n"]
                                con.execute("DELETE FROM movements WHERE item_id=%s", (row["id"],))
                                con.execute("DELETE FROM items WHERE id=%s", (row["id"],))
                                con.commit()
                                log_action(user["username"], "刪除料號", f"{code}；一併刪除庫存異動紀錄 {count} 筆")
                                st.success(f"失效料號 {code} 已刪除，並一併刪除 {count} 筆異動紀錄。")
                                st.rerun()

    elif page == "人員與權限":
        st.title("人員與權限")
        # 密碼修改表單已統一放在側邊欄，避免同一個 Streamlit form key 重複建立。
        require_system_admin()
        st.divider()
        st.caption("帳號建立後立即生效；員工自行註冊的帳號預設為員工權限。")
        with connect() as con:
            existing_users = con.execute("SELECT username,display_name,role,active FROM users ORDER BY username").fetchall()
        options = ["建立新帳號"] + [f"{r['username']} | {r['display_name']}" for r in existing_users]
        mode = st.radio("操作", ["建立帳號", "更新帳號"], horizontal=True, key="account_mode")
        selected = None
        default_department = "生技"
        if mode == "更新帳號" and existing_users:
            selected = st.selectbox("選擇要更新的帳號", options[1:], key="account_update_select")
            uname = selected.split(" | ", 1)[0]
            with connect() as con:
                row = con.execute("SELECT username,display_name,role,active FROM users WHERE username=%s", (uname,)).fetchone()
                staff_row = con.execute("SELECT department FROM staff WHERE name=%s", (row["display_name"],)).fetchone()
            default_username, default_display, default_role, default_active = row["username"], row["display_name"], normalize_role(row["role"]), bool(row["active"])
            if staff_row and staff_row["department"] in ["生技", "品保", "製造"]:
                default_department = staff_row["department"]
        else:
            default_username, default_display, default_role, default_active = "", "", "employee", True
        with st.form("user_create_update"):
            account_username = st.text_input("工號 / 登入帳號", value=default_username, disabled=(mode == "更新帳號"))
            st.text_input("顯示名稱（自動使用工號）", value=(default_username if mode == "更新帳號" else ""), disabled=True)
            account_password = st.text_input("密碼（建立必填；更新留空代表不修改）", type="password")
            dept_options = ["生技", "品保", "製造"]
            account_department = st.selectbox("部門", dept_options, index=dept_options.index(default_department))
            role_options = ["system_admin", "manager", "employee"]
            account_role = st.selectbox("權限", role_options, index=role_options.index(default_role), format_func=lambda x: ROLE_LABELS[x])
            account_active = st.checkbox("啟用帳號", value=default_active)
            save_account = st.form_submit_button("建立帳號" if mode == "建立帳號" else "更新帳號")
        if save_account:
            uname = account_username.strip()
            display = uname
            if not uname:
                st.error("登入帳號不可空白。")
            elif mode == "建立帳號" and len(account_password) < (12 if account_role == "system_admin" else 10):
                st.error("建立系統管理員帳號時密碼至少需要 12 個字元；其他帳號至少 10 個字元。")
            elif account_password and len(account_password) < (12 if account_role == "system_admin" else 10):
                st.error("系統管理員密碼至少 12 個字元；其他帳號至少 10 個字元，或留空以保留原密碼。")
            elif uname == user["username"] and not account_active:
                st.error("不能停用目前登入中的帳號。")
            else:
                try:
                    with connect() as con:
                        if mode == "更新帳號":
                            current = con.execute("SELECT role,active FROM users WHERE username=%s", (uname,)).fetchone()
                            active_admin_count = con.execute(
                                "SELECT COUNT(*) AS n FROM users WHERE role='system_admin' AND active=1"
                            ).fetchone()["n"]
                            if current and current["role"] == "system_admin" and int(current["active"]) == 1 and active_admin_count <= 1 and (account_role != "system_admin" or not account_active):
                                st.error("不能停用或降權最後一個啟用中的系統管理員。")
                                st.stop()
                        if mode == "建立帳號":
                            salt, digest = hash_password(account_password)
                            con.execute("""INSERT INTO users(username,display_name,salt,password_hash,role,active,created_at)
                                          VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                                         (uname, display, salt, digest, account_role, 1 if account_active else 0, now_str()))
                            action = "建立帳號"
                        else:
                            if account_password:
                                salt, digest = hash_password(account_password)
                                con.execute("""UPDATE users SET display_name=%s,salt=%s,password_hash=%s,role=%s,active=%s
                                              WHERE username=%s""",
                                            (display, salt, digest, account_role, 1 if account_active else 0, uname))
                            else:
                                con.execute("UPDATE users SET display_name=%s,role=%s,active=%s WHERE username=%s",
                                            (display, account_role, 1 if account_active else 0, uname))
                            action = "更新帳號"
                        con.execute("""INSERT INTO staff(name,department,active) VALUES(%s,%s,1)
                                      ON CONFLICT(name) DO UPDATE SET department=excluded.department,active=1""",
                                    (display, account_department))
                        con.commit()
                    log_action(user["username"], action, f"{uname} / {account_role}")
                    st.success("帳號已儲存。")
                    st.rerun()
                except psycopg.IntegrityError:
                    st.error("此登入帳號已存在，請檢查工號。")
        st.divider()
        st.subheader("登入帳號清單")
        with connect() as con:
            usersdf = query_df("SELECT username AS 工號,display_name AS 顯示名稱,role AS 權限,CASE active WHEN 1 THEN '有效' ELSE '停用' END AS 狀態,created_at AS 建立時間 FROM users ORDER BY username", con)
        usersdf["權限"] = usersdf["權限"].map(lambda r: ROLE_LABELS.get(r, r))
        usersdf["密碼"] = "不可查看（安全雜湊儲存；可重設）"
        st.dataframe(usersdf, use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("刪除登入帳號")
        st.warning("不能刪除目前登入帳號，也不能刪除最後一個啟用中的系統管理員。")
        with connect() as con:
            deletable = con.execute("SELECT username,display_name,role FROM users WHERE role <> 'system_admin' ORDER BY username").fetchall()
        delete_options = [f"{r['username']} | {r['display_name']} | {ROLE_LABELS.get(r['role'], r['role'])}" for r in deletable]
        if delete_options:
            chosen = st.selectbox("選擇要刪除的帳號", delete_options, key="account_delete_select")
            confirm = st.checkbox("我確認永久刪除此登入帳號", key="confirm_account_delete")
            if st.button("刪除帳號", type="secondary"):
                target_username = chosen.split(" | ", 1)[0]
                if not confirm:
                    st.error("請先勾選確認框。")
                elif target_username == user["username"]:
                    st.error("不能刪除目前登入的帳號。")
                else:
                    with connect() as con:
                        con.execute("DELETE FROM users WHERE username=%s AND role <> 'system_admin'", (target_username,))
                        con.commit()
                    log_action(user["username"], "刪除帳號", target_username)
                    st.success("帳號已刪除。")
                    st.rerun()
        else:
            st.caption("目前沒有可刪除的非系統管理員帳號。")

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
                    file_name=f"spares_postgres_backup_{datetime.now(VN_TZ):%Y%m%d_%H%M%S}.json",
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

# 中越雙語切換（沿用本地 V2.3 介面）
bilingual_sidebar()
if "user" not in st.session_state:
    login_screen()
else:
    main_app()
