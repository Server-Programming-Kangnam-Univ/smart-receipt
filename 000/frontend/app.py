import gradio as gr
import requests
import pandas as pd
import io
from PIL import Image
from datetime import date
import json

API_URL = "http://localhost:8000/analyze-receipt/"
HISTORY_URL = "http://localhost:8000/history/"
ASK_AI_URL = "http://localhost:8000/ask-ai/"
BUDGET_URL = "http://localhost:8000/budget/"

custom_css = """
body { background-color: #f8fafc !important; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.dashboard-card {
    background: white !important; border-radius: 16px !important; padding: 24px !important;
    border: 1px solid #e2e8f0 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    margin-bottom: 20px !important;
}
.card-title { font-size: 1.1rem; font-weight: 700; color: #1e293b; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }
.budget-amount { font-size: 1.8rem; font-weight: 800; color: #1e293b; margin-bottom: 8px; }
.budget-amount span { font-size: 1rem; color: #64748b; font-weight: 500; }
.progress-container { background: #e2e8f0; border-radius: 9999px; height: 12px; width: 100%; margin-bottom: 8px; }
.progress-bar { background: #3b82f6; height: 100%; border-radius: 9999px; transition: width 0.3s ease; }
.receipt-image-container { 
    border: 2px dashed #e2e8f0; border-radius: 12px; padding: 10px; 
    background: #f1f5f9; min-height: 200px; display: flex; align-items: center; justify-content: center;
}
"""

def fetch_history():
    try:
        response = requests.get(HISTORY_URL)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []

def fetch_budget():
    try:
        response = requests.get(BUDGET_URL)
        if response.status_code == 200:
            return response.json().get("budget", 1000000)
    except Exception:
        pass
    return 1000000

def set_budget(new_budget):
    try:
        response = requests.post(BUDGET_URL, json={"budget": int(new_budget)})
        if response.status_code == 200:
            return int(new_budget), "✅ 예산이 저장되었습니다."
    except Exception as e:
        return 1000000, f"❌ 오류: {str(e)}"
    return 1000000, "❌ 저장 실패"

def get_budget_html(spent=0, total=1000000):
    percent = min(int((spent / total) * 100), 100) if total > 0 else 0
    color = "#3b82f6" if percent < 80 else "#ef4444" 
    return f"""
    <div class="budget-amount">₩{spent:,} <span>/ 예산 ₩{total:,}</span></div>
    <div class="progress-container"><div class="progress-bar" style="width: {percent}%; background-color: {color};"></div></div>
    <div style="text-align: right; font-weight: 700; color: #64748b;">{percent}% 사용됨</div>
    """

def prepare_chart_data(history):
    if not history:
        return pd.DataFrame({"월": [], "지출액": []})
    monthly_data = {}
    for r in history:
        m = r.get('date', '2026-06-08')[:7]
        monthly_data[m] = monthly_data.get(m, 0) + r.get('total_amount', 0)
    sorted_months = sorted(monthly_data.keys())
    return pd.DataFrame({"월": sorted_months, "지출액": [monthly_data[m] for m in sorted_months]})

def update_dashboard(history, budget):
    total_spent = sum(r.get('total_amount', 0) for r in history)
    cat_counts = {}
    for r in history:
        cat = r.get('top_category', '기타')
        cat_counts[cat] = cat_counts.get(cat, 0) + r.get('total_amount', 0)
    chart_df = prepare_chart_data(history)
    return get_budget_html(total_spent, budget), cat_counts, chart_df

def update_table(history, search_query=""):
    filtered = history
    if search_query:
        q = search_query.lower()
        filtered = [r for r in history if q in r.get('store_name','').lower() or q in r.get('top_category','').lower()]
    rows = [[r.get('date'), r.get('store_name'), r.get('top_category'), f"₩{r.get('total_amount',0):,}", "✅"] for r in filtered]
    return pd.DataFrame(rows, columns=["날짜", "가맹점명", "카테고리", "금액", "상태"])

def show_receipt_image(evt: gr.SelectData, history):
    try:
        idx = evt.index[0]
        image_url = history[idx].get("image_url")
        if image_url:
            return gr.update(value=image_url, visible=True)
    except Exception:
        pass
    return gr.update(value=None, visible=False)

def process_multiple_receipts(files, history):
    if not files:
        return history, "파일을 업로드해주세요."
    new_results = []
    errors = 0
    for file_path in files:
        try:
            with open(file_path, "rb") as f:
                img_bytes = f.read()
            res = requests.post(API_URL, files={'file': ('image.png', img_bytes, 'image/png')})
            if res.status_code == 200:
                new_results.append(res.json())
            else:
                errors += 1
        except Exception:
            errors += 1
    updated_history = fetch_history()
    msg = f"{len(new_results)}건 분석 완료" + (f" (오류 {errors}건)" if errors > 0 else "")
    return updated_history, msg

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
    chat_history.append((user_input, answer))
    return "", chat_history

def export_to_csv(history):
    if not history:
        return None
    df = pd.DataFrame(history)
    file_path = "receipts_export.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path

with gr.Blocks(css=custom_css, title="영수증 AI 비서") as demo:
    history_state = gr.State(fetch_history())
    budget_state = gr.State(fetch_budget())
    
    with gr.Column(elem_classes="container"):
        gr.HTML("<h1 style='color: #1e293b; margin-bottom: 24px;'>🧾 영수증 AI 소비 비서</h1>")
        
        with gr.Tabs():
            with gr.Tab("📊 대시보드"):
                with gr.Row():
                    with gr.Column(scale=2, elem_classes="dashboard-card"):
                        gr.HTML("<div class='card-title'>💰 지출 현황 및 예산 설정</div>")
                        with gr.Row():
                            budget_view = gr.HTML()
                            with gr.Column():
                                budget_input = gr.Number(label="월 목표 예산 설정", value=1000000, step=10000)
                                budget_btn = gr.Button("예산 저장", variant="secondary")
                                budget_msg = gr.Markdown("")
                        
                    with gr.Column(scale=1, elem_classes="dashboard-card"):
                        gr.HTML("<div class='card-title'>🍩 카테고리 비율</div>")
                        cat_label = gr.Label(show_label=False)
                
                with gr.Column(elem_classes="dashboard-card"):
                    gr.HTML("<div class='card-title'>📈 월별 지출 트렌드</div>")
                    trend_chart = gr.BarPlot(x="월", y="지출액", tooltip=["월", "지출액"], vertical=False, height=300)

            with gr.Tab("📸 영수증 올리기"):
                with gr.Row():
                    with gr.Column(scale=1):
                        uploader = gr.File(file_count="multiple", file_types=["image"], label="영수증 이미지 업로드")
                        analyze_btn = gr.Button("🚀 AI 분석 시작", variant="primary")
                    with gr.Column(scale=1):
                        status_msg = gr.Textbox(label="처리 상태", interactive=False)
                        latest_analysis = gr.JSON(label="최근 분석 결과")

            with gr.Tab("🤖 AI 소비 비서"):
                chatbot = gr.Chatbot(label="소비 상담", height=500)
                with gr.Row():
                    chat_input = gr.Textbox(show_label=False, placeholder="질문을 입력하세요...", scale=9)
                    send_btn = gr.Button("전송", scale=1)

            with gr.Tab("📁 영수증 보관함"):
                with gr.Row():
                    with gr.Column(scale=2):
                        with gr.Row():
                            search_box = gr.Textbox(show_label=False, placeholder="가맹점 또는 카테고리 검색...", scale=4)
                            export_btn = gr.Button("📥 CSV 내보내기", scale=1)
                        gr.Markdown("*(내역을 클릭하면 영수증 원본 이미지를 볼 수 있습니다)*")
                        receipt_table = gr.Dataframe(interactive=False)
                    with gr.Column(scale=1, elem_classes="dashboard-card"):
                        gr.HTML("<div class='card-title'>🖼️ 영수증 원본 미리보기</div>")
                        receipt_img_viewer = gr.Image(label="원본 이미지", interactive=False, visible=True)
                
                download_file = gr.File(label="다운로드", visible=False)

    def refresh_all(history, budget):
        b_html, c_data, t_df = update_dashboard(history, budget)
        table_df = update_table(history)
        return b_html, c_data, t_df, table_df, budget

    demo.load(
        fn=lambda h, b: refresh_all(h, b),
        inputs=[history_state, budget_state],
        outputs=[budget_view, cat_label, trend_chart, receipt_table, budget_input]
    )

    budget_btn.click(
        fn=set_budget,
        inputs=[budget_input],
        outputs=[budget_state, budget_msg]
    ).then(
        fn=refresh_all,
        inputs=[history_state, budget_state],
        outputs=[budget_view, cat_label, trend_chart, receipt_table, budget_input]
    )

    analyze_btn.click(
        process_multiple_receipts, 
        inputs=[uploader, history_state], 
        outputs=[history_state, status_msg]
    ).then(
        fn=refresh_all,
        inputs=[history_state, budget_state],
        outputs=[budget_view, cat_label, trend_chart, receipt_table, budget_input]
    )

    search_box.change(update_table, inputs=[history_state, search_box], outputs=[receipt_table])
    receipt_table.select(show_receipt_image, inputs=[history_state], outputs=[receipt_img_viewer])

    export_btn.click(export_to_csv, inputs=[history_state], outputs=[download_file]).then(
        lambda: gr.update(visible=True), None, download_file
    )

    chat_input.submit(chat_with_ai, inputs=[chat_input, chatbot], outputs=[chat_input, chatbot])
    send_btn.click(chat_with_ai, inputs=[chat_input, chatbot], outputs=[chat_input, chatbot])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())
