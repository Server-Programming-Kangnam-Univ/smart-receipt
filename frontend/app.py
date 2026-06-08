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
BUDGET = 1_000_000

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

def get_budget_html(spent=0, total=BUDGET):
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

def update_home():
    data = fetch_data()
    total_spent = sum(r.get('analysis', {}).get('total_amount', 0) for r in data)
    table_rows = []
    category_counts = {}
    latest_report = "영수증을 업로드하면 AI 소비 분석이 시작됩니다."
    
    for r in reversed(data):
        analysis = r.get('analysis', {})
        amount = analysis.get('total_amount', 0)
        cat = analysis.get('top_category', '기타')
        category_counts[cat] = category_counts.get(cat, 0) + amount
        table_rows.append([r.get('created_at', '').split('T')[0], analysis.get('most_expensive_item', '-'), cat, f"₩{amount:,}", "✅ 완료"])
        if latest_report == "영수증을 업로드하면 AI 소비 분석이 시작됩니다.":
            latest_report = analysis.get('analysis', latest_report)

    df = pd.DataFrame(table_rows, columns=["날짜", "주요품목", "카테고리", "금액", "상태"])
    if df.empty:
        df = pd.DataFrame([["", "", "", "₩", ""]], columns=["날짜", "주요품목", "카테고리", "금액", "상태"])
    
    cat_ratio = {k: v for k, v in category_counts.items()}
    return df, get_budget_html(total_spent), cat_ratio, f"<div class='report-card'><b>🤖 AI 소비 리포트</b><br>{latest_report}</div>"

def update_analysis():
    data = fetch_data()
    if not data:
        return px.bar(title="데이터가 없습니다."), px.pie(title="데이터가 없습니다.")
    
    df_list = []
    for r in data:
        analysis = r.get('analysis', {})
        df_list.append({
            "날짜": r.get('created_at', '').split('T')[0],
            "금액": analysis.get('total_amount', 0),
            "카테고리": analysis.get('top_category', '기타')
        })
    
    df = pd.DataFrame(df_list)
    fig_bar = px.bar(df.groupby("카테고리")["금액"].sum().reset_index(), x="카테고리", y="금액", title="카테고리별 지출 합계")
    fig_pie = px.pie(df, values="금액", names="카테고리", title="지출 비율")
    return fig_bar, fig_pie

def update_storage():
    data = fetch_data()
    gallery_items = []
    for r in data:
        img_url = f"{BASE_URL}{r['image_url']}"
        info = f"{r['created_at'].split('T')[0]}\n{r['analysis'].get('total_amount', 0):,}원"
        gallery_items.append((img_url, info))
    return gallery_items

def bulk_upload(files):
    if not files: return update_storage()
    for f in files:
        with open(f.name, 'rb') as file_data:
            files_payload = {'file': (f.name, file_data, 'image/png')}
            requests.post(ANALYZE_URL, files=files_payload)
    return update_storage()

with gr.Blocks(css=custom_css, theme=gr.themes.Soft()) as demo:
    with gr.Column(elem_classes="container"):
        gr.HTML('<div class="navbar"><div class="nav-logo">🧾 영수증 AI</div></div>')
        
        with gr.Tabs() as tabs:
            with gr.Tab("🏠 홈", id="home"):
                gr.HTML("<div class='welcome-text'>👋 안녕하세요</div>")
                report_box = gr.HTML()
                with gr.Row():
                    with gr.Column(elem_classes="dashboard-card"):
                        gr.HTML("<b>📊 이달의 누적 지출</b>")
                        budget_viewer = gr.HTML()
                    with gr.Column(elem_classes="dashboard-card"):
                        gr.HTML("<b>🍩 카테고리별 소비 비율</b>")
                        cat_label = gr.Label(show_label=False)
                with gr.Column(elem_classes="dashboard-card"):
                    gr.Markdown("### 📸 최근 업로드 내역")
                    receipt_table = gr.Dataframe(interactive=False)

            with gr.Tab("📈 소비분석", id="analysis"):
                with gr.Row():
                    chart_bar = gr.Plot()
                    chart_pie = gr.Plot()
                refresh_analysis = gr.Button("통계 새로고침", variant="primary")

            with gr.Tab("📁 영수증보관함", id="storage"):
                with gr.Row():
                    with gr.Column(elem_classes="dashboard-card", scale=1):
                        gr.Markdown("### 📤 여러 영수증 한꺼번에 올리기")
                        file_input = gr.File(file_count="multiple", label="이미지 선택")
                        upload_btn = gr.Button("업로드 및 분석 시작", variant="primary")
                    
                    with gr.Column(elem_classes="dashboard-card", scale=1):
                        gr.Markdown("### ✍️ 직접 입력하기")
                        m_date = gr.Textbox(label="날짜", value=datetime.now().strftime("%Y-%m-%d"), placeholder="YYYY-MM-DD")
                        m_merchant = gr.Textbox(label="가맹점명", placeholder="예: 스타벅스")
                        m_category = gr.Dropdown(label="카테고리", choices=["식비", "교통비", "생필품", "문화생활", "전자기기", "기타"], value="기타")
                        m_amount = gr.Number(label="금액", value=0)
                        m_status = gr.Textbox(label="상태 (공란 가능)", placeholder="예: 현금결제")
                        manual_btn = gr.Button("내역 추가", variant="secondary")

                receipt_gallery = gr.Gallery(label="내 영수증 목록", columns=4, height="auto")

    # Events
    def add_manual_entry(date_str, merchant, category, amount, status):
        try:
            payload = {
                "date": date_str,
                "merchant": merchant,
                "category": category,
                "amount": amount,
                "status": status
            }
            res = requests.post(f"{BASE_URL}/receipts/manual/", json=payload)
            if res.status_code == 200:
                return update_storage()
        except:
            pass
        return update_storage()

    demo.load(update_home, None, [receipt_table, budget_viewer, cat_label, report_box])
    tabs.select(fn=update_home, outputs=[receipt_table, budget_viewer, cat_label, report_box])
    
    refresh_analysis.click(update_analysis, None, [chart_bar, chart_pie])
    tabs.select(fn=update_analysis, outputs=[chart_bar, chart_pie])
    
    upload_btn.click(bulk_upload, inputs=file_input, outputs=receipt_gallery).then(
        update_home, None, [receipt_table, budget_viewer, cat_label, report_box]
    )
    
    manual_btn.click(add_manual_entry, inputs=[m_date, m_merchant, m_category, m_amount, m_status], outputs=receipt_gallery).then(
        update_home, None, [receipt_table, budget_viewer, cat_label, report_box]
    )

    tabs.select(fn=update_storage, outputs=receipt_gallery)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
