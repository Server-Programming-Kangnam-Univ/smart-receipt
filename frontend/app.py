import gradio as gr
import requests
import pandas as pd
import io
import plotly.express as px
from PIL import Image
from datetime import datetime

# Backend API URLs
BASE_URL = "http://localhost:8000"
ANALYZE_URL = f"{BASE_URL}/analyze-receipt/"
BULK_ANALYZE_URL = f"{BASE_URL}/analyze-receipts-bulk/"
RECEIPTS_URL = f"{BASE_URL}/receipts/"
BUDGET_URL = f"{BASE_URL}/budget/"
ASK_AI_URL = f"{BASE_URL}/ask-ai/"

custom_css = """
body { background-color: #f4f6f9 !important; }
.container { max-width: 1100px; margin: 0 auto; padding: 20px 15px; }
.navbar {
    display: flex; justify-content: space-between; align-items: center;
    background: white; padding: 15px 30px; border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 25px;
}
.nav-logo { font-size: 1.3rem; font-weight: 800; color: #1e293b; }
.dashboard-card {
    background: white !important; border-radius: 16px !important; padding: 24px !important;
    border: 1px solid #e2e8f0 !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.01) !important;
    margin-bottom: 20px !important; 
}
.welcome-text { font-size: 1.6rem; font-weight: 700; color: #0f172a; margin-bottom: 15px; }
.report-card {
    background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px;
    padding: 16px 20px; margin-bottom: 25px;
}
.budget-amount { font-size: 1.6rem; font-weight: 800; color: #1e293b; margin-bottom: 12px; }
.progress-container { background: #e2e8f0; border-radius: 9999px; height: 12px; width: 100%; position: relative; margin-bottom: 8px; }
.progress-bar { background: #3b82f6; height: 100%; border-radius: 9999px; }
"""

def fetch_budget():
    try:
        res = requests.get(BUDGET_URL)
        if res.status_code == 200:
            return res.json().get("budget", 1000000)
    except Exception:
        pass
    return 1000000

def set_budget(new_budget):
    try:
        res = requests.post(BUDGET_URL, json={"budget": int(new_budget)})
        if res.status_code == 200:
            return int(new_budget), "예산이 저장되었습니다."
    except Exception as e:
        return 1000000, f"오류: {str(e)}"
    return 1000000, "저장 실패"

def get_budget_html(spent=0, total=1000000):
    percent = int((spent / total) * 100) if total > 0 else 0
    if percent > 100: percent = 100
    return f"""
    <div class="budget-amount">₩{spent:,} <span>/ 예산 ₩{total:,}</span></div>
    <div class="progress-container"><div class="progress-bar" style="width: {percent}%;"></div></div>
    <div class="progress-percent">{percent}%</div>
    """

def fetch_data():
    try:
        response = requests.get(RECEIPTS_URL)
        if response.status_code == 200:
            return response.json()
    except:
        return []
    return []

def _get_amount(analysis):
    return analysis.get('payment_info', {}).get('total_price', 0)

def _get_category(analysis):
    items = analysis.get('items', [])
    cats = [i.get('category') for i in items if i.get('category')]
    return max(set(cats), key=cats.count) if cats else '기타'

def _get_store(analysis):
    return analysis.get('store_info', {}).get('name') or '-'

def _get_date(r, analysis):
    return analysis.get('payment_info', {}).get('date') or r.get('created_at', '').split('T')[0]

def update_home():
    data = fetch_data()
    budget = fetch_budget()
    total_spent = sum(_get_amount(r.get('analysis', {})) for r in data)
    table_rows = []
    category_counts = {}
    latest_report = "영수증을 업로드하면 AI 소비 분석이 시작됩니다."

    for r in reversed(data):
        analysis = r.get('analysis', {})
        amount = _get_amount(analysis)
        cat = _get_category(analysis)
        category_counts[cat] = category_counts.get(cat, 0) + amount
        table_rows.append([_get_date(r, analysis), _get_store(analysis), cat, f"₩{amount:,}", "✅ 완료"])

    df = pd.DataFrame(table_rows, columns=["날짜", "주요품목", "카테고리", "금액", "상태"])
    if df.empty:
        df = pd.DataFrame([["", "", "", "₩", ""]], columns=["날짜", "주요품목", "카테고리", "금액", "상태"])

    cat_ratio = {k: v for k, v in category_counts.items()}
    return df, get_budget_html(total_spent, budget), cat_ratio, f"<div class='report-card'><b>AI 소비 리포트</b><br>{latest_report}</div>", budget

def update_analysis():
    data = fetch_data()
    if not data:
        return px.bar(title="데이터가 없습니다."), px.pie(title="데이터가 없습니다.")

    df_list = []
    for r in data:
        analysis = r.get('analysis', {})
        df_list.append({
            "날짜": _get_date(r, analysis),
            "금액": _get_amount(analysis),
            "카테고리": _get_category(analysis),
        })

    df = pd.DataFrame(df_list)
    fig_bar = px.bar(df.groupby("카테고리")["금액"].sum().reset_index(), x="카테고리", y="금액", title="카테고리별 지출 합계")
    fig_pie = px.pie(df, values="금액", names="카테고리", title="지출 비율")
    return fig_bar, fig_pie

def update_storage():
    data = fetch_data()
    gallery_items = []
    for r in data:
        if not r.get('image_url'):
            continue
        img_url = f"{BASE_URL}{r['image_url']}"
        analysis = r.get('analysis', {})
        amount = _get_amount(analysis)
        info = f"{_get_date(r, analysis)}\n{amount:,}원"
        gallery_items.append((img_url, info))
    return gallery_items

def bulk_upload(files):
    if not files:
        return update_storage()
    for f in files:
        path = f if isinstance(f, str) else f.name
        with open(path, 'rb') as file_data:
            files_payload = {'file': (path, file_data, 'image/png')}
            requests.post(ANALYZE_URL, files=files_payload)
    return update_storage()

def delete_receipt_ui(receipt_id):
    if not receipt_id:
        return update_storage()
    try:
        actual_id = receipt_id.split("ID: ")[-1] if "ID: " in receipt_id else receipt_id
        res = requests.delete(f"{RECEIPTS_URL}{actual_id}")
        if res.status_code == 200:
            print(f"Deleted: {actual_id}")
    except Exception as e:
        print(f"Delete error: {e}")
    return update_storage()

def get_receipt_choices():
    data = fetch_data()
    choices = []
    for r in reversed(data):
        analysis = r.get('analysis', {})
        date = _get_date(r, analysis)
        store = _get_store(analysis)
        choices.append(f"{date} | {store} (ID: {r['id']})")
    return choices

def chat_with_ai(user_input, chat_history):
    if not user_input:
        return "", chat_history
    try:
        res = requests.post(ASK_AI_URL, json={"question": user_input})
        if res.status_code == 200:
            answer = res.json().get("answer", "죄송합니다.")
        else:
            answer = f"오류: {res.status_code}"
    except Exception as e:
        answer = f"연결 오류: {str(e)}"
    chat_history.append({"role": "user", "content": user_input})
    chat_history.append({"role": "assistant", "content": answer})
    return "", chat_history

def export_to_csv():
    data = fetch_data()
    if not data:
        return None
    rows = []
    for r in data:
        analysis = r.get('analysis', {})
        rows.append({
            "날짜": _get_date(r, analysis),
            "가맹점": _get_store(analysis),
            "카테고리": _get_category(analysis),
            "금액": _get_amount(analysis),
        })
    df = pd.DataFrame(rows)
    file_path = "receipts_export.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path


with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
    with gr.Column(elem_classes="container"):

        # ── 내비게이션 버튼 바 ──
        with gr.Row():
            gr.HTML('<div class="nav-logo">영수증 AI</div>')
            btn_home     = gr.Button("홈",           variant="primary",   size="sm", scale=0)
            btn_analysis = gr.Button("소비분석",     variant="secondary", size="sm", scale=0)
            btn_chat     = gr.Button("AI 소비 비서", variant="secondary", size="sm", scale=0)
            btn_storage  = gr.Button("영수증보관함", variant="secondary", size="sm", scale=0)

        # ── 페이지 1: 홈 ──
        with gr.Column(visible=True) as page_home:
            gr.HTML("<div class='welcome-text'>안녕하세요</div>")
            report_box = gr.HTML()
            with gr.Row():
                with gr.Column(elem_classes="dashboard-card"):
                    gr.HTML("<b>이달의 누적 지출</b>")
                    budget_viewer = gr.HTML()
                    with gr.Row():
                        budget_input = gr.Number(label="월 목표 예산 설정", value=1000000, step=10000)
                        budget_btn   = gr.Button("예산 저장", variant="secondary", scale=0)
                    budget_msg = gr.Markdown("")
                with gr.Column(elem_classes="dashboard-card"):
                    gr.HTML("<b>카테고리별 소비 비율</b>")
                    cat_label = gr.JSON(label="")
            with gr.Column(elem_classes="dashboard-card"):
                gr.Markdown("### 최근 업로드 내역")
                receipt_table = gr.Dataframe(interactive=False)

        # ── 페이지 2: 소비분석 ──
        with gr.Column(visible=False) as page_analysis:
            with gr.Row():
                chart_bar = gr.Plot()
                chart_pie = gr.Plot()
            refresh_analysis = gr.Button("통계 새로고침", variant="primary")

        # ── 페이지 3: AI 소비 비서 ──
        with gr.Column(visible=False) as page_chat:
            chatbot = gr.Chatbot(label="소비 상담", height=500)
            with gr.Row():
                chat_input = gr.Textbox(show_label=False, placeholder="질문을 입력하세요...", scale=9)
                send_btn   = gr.Button("전송", scale=1)

        # ── 페이지 4: 영수증보관함 ──
        with gr.Column(visible=False) as page_storage:
            with gr.Row():
                with gr.Column(elem_classes="dashboard-card", scale=1):
                    gr.Markdown("### 여러 영수증 한꺼번에 올리기")
                    file_input = gr.File(file_count="multiple", label="이미지 선택")
                    upload_btn = gr.Button("업로드 및 분석 시작", variant="primary")
                with gr.Column(elem_classes="dashboard-card", scale=1):
                    gr.Markdown("### 직접 입력하기")
                    m_date     = gr.Textbox(label="날짜", value=datetime.now().strftime("%Y-%m-%d"), placeholder="YYYY-MM-DD")
                    m_merchant = gr.Textbox(label="가맹점명", placeholder="예: 스타벅스")
                    m_category = gr.Dropdown(label="카테고리", choices=["식비","교통비","생필품","문화생활","전자기기","기타"], value="기타")
                    m_amount   = gr.Number(label="금액", value=0)
                    m_status   = gr.Textbox(label="상태 (공란 가능)", placeholder="예: 현금결제")
                    manual_btn = gr.Button("내역 추가", variant="secondary")
            with gr.Column(elem_classes="dashboard-card"):
                gr.Markdown("### 내역 삭제하기")
                with gr.Row():
                    delete_select   = gr.Dropdown(label="삭제할 영수증 선택", choices=get_receipt_choices())
                    refresh_del_btn = gr.Button("목록 갱신", scale=0)
                    delete_btn      = gr.Button("선택한 내역 삭제", variant="stop", scale=1)
            with gr.Row():
                export_btn    = gr.Button("CSV 내보내기", variant="secondary")
                download_file = gr.File(label="다운로드", visible=False)
            receipt_gallery = gr.Gallery(label="내 영수증 목록", columns=4, height="auto")

    # ── 이벤트 ──
    pages        = [page_home, page_analysis, page_chat, page_storage]
    home_outputs = [receipt_table, budget_viewer, cat_label, report_box, budget_input]

    def _pages(show_idx):
        return [gr.update(visible=(i == show_idx)) for i in range(4)]

    def go_home():
        return _pages(0) + list(update_home())

    def go_analysis():
        return _pages(1) + list(update_analysis())

    def go_chat():
        return _pages(2)

    def go_storage():
        return _pages(3) + [update_storage()]

    btn_home.click(    fn=go_home,     outputs=pages + home_outputs)
    btn_analysis.click(fn=go_analysis, outputs=pages + [chart_bar, chart_pie])
    btn_chat.click(    fn=go_chat,     outputs=pages)
    btn_storage.click( fn=go_storage,  outputs=pages + [receipt_gallery])

    demo.load(update_home, None, home_outputs)

    def on_budget_save(new_budget):
        saved_budget, msg = set_budget(new_budget)
        data = fetch_data()
        total_spent = sum(_get_amount(r.get('analysis', {})) for r in data)
        return get_budget_html(total_spent, saved_budget), msg

    budget_btn.click(on_budget_save, inputs=[budget_input], outputs=[budget_viewer, budget_msg])
    refresh_analysis.click(update_analysis, None, [chart_bar, chart_pie])

    chat_input.submit(chat_with_ai, inputs=[chat_input, chatbot], outputs=[chat_input, chatbot])
    send_btn.click(   chat_with_ai, inputs=[chat_input, chatbot], outputs=[chat_input, chatbot])

    def add_manual_entry(date_str, merchant, category, amount, status):
        try:
            payload = {"date": date_str, "merchant": merchant, "category": category, "amount": amount, "status": status}
            requests.post(f"{BASE_URL}/receipts/manual/", json=payload)
        except Exception:
            pass
        return update_storage(), gr.update(choices=get_receipt_choices())

    def refresh_delete_list():
        return gr.update(choices=get_receipt_choices())

    upload_btn.click(bulk_upload, inputs=file_input, outputs=receipt_gallery).then(
        update_home, None, home_outputs
    ).then(refresh_delete_list, None, delete_select)

    manual_btn.click(
        add_manual_entry,
        inputs=[m_date, m_merchant, m_category, m_amount, m_status],
        outputs=[receipt_gallery, delete_select]
    ).then(update_home, None, home_outputs)

    delete_btn.click(delete_receipt_ui, inputs=delete_select, outputs=receipt_gallery).then(
        update_home, None, home_outputs
    ).then(refresh_delete_list, None, delete_select)

    refresh_del_btn.click(refresh_delete_list, None, delete_select)

    export_btn.click(export_to_csv, None, download_file).then(
        lambda: gr.update(visible=True), None, download_file
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
