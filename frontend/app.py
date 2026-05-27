import gradio as gr
import requests
import pandas as pd
import io
from PIL import Image
from datetime import date

API_URL = "http://localhost:8000/analyze-receipt/"
BUDGET = 1_000_000  # 기본 월 예산 100만원

custom_css = """
body { background-color: #f4f6f9 !important; }
.container { max-width: 1100px; margin: 0 auto; padding: 20px 15px; }

.navbar {
    display: flex; justify-content: space-between; align-items: center;
    background: white; padding: 15px 30px; border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 25px;
}
.nav-logo { font-size: 1.3rem; font-weight: 800; color: #1e293b; display: flex; align-items: center; gap: 8px; }
.nav-menu { display: flex; gap: 25px; font-weight: 600; color: #64748b; }
.nav-menu .active { color: #3b82f6; border-bottom: 2px solid #3b82f6; padding-bottom: 2px; }
.nav-user { display: flex; align-items: center; gap: 8px; font-weight: 600; color: #1e293b; }

.welcome-text { font-size: 1.6rem; font-weight: 700; color: #0f172a; margin-bottom: 15px; }
.report-card {
    background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px;
    padding: 16px 20px; margin-bottom: 25px;
}
.report-title { font-weight: 700; color: #1e40af; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
.report-desc { color: #1e3a8a; font-size: 1.05rem; }

.dashboard-card {
    background: white !important; border-radius: 16px !important; padding: 24px !important;
    border: 1px solid #e2e8f0 !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.01) !important;
    height: 100%;
    margin-bottom: 20px !important;
}
.card-title { font-size: 1.1rem; font-weight: 700; color: #1e293b; margin-bottom: 15px; display: flex; align-items: center; gap: 6px; }

.budget-amount { font-size: 1.6rem; font-weight: 800; color: #1e293b; margin-bottom: 12px; }
.budget-amount span { font-size: 1rem; color: #94a3b8; font-weight: 500; }
.progress-container { background: #e2e8f0; border-radius: 9999px; height: 12px; width: 100%; position: relative; margin-bottom: 8px; }
.progress-bar { background: #3b82f6; height: 100%; border-radius: 9999px; transition: width 0.3s ease; }
.progress-percent { text-align: right; font-size: 0.9rem; font-weight: 700; color: #64748b; }

.table-header-flex { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.table-header-flex h3 { margin: 0 !important; }
"""

initial_data = pd.DataFrame(
    [["", "", "", "₩", ""], ["", "", "", "₩", ""]],
    columns=["날짜", "가맹점명", "카테고리", "금액", "상태"]
)

def get_budget_html(spent=0, total=BUDGET):
    percent = int((spent / total) * 100) if total > 0 else 0
    return f"""
    <div class="budget-amount">₩{spent:,} <span>/ 예산 ₩{total:,}</span></div>
    <div class="progress-container">
        <div class="progress-bar" style="width: {percent}%;"></div>
    </div>
    <div class="progress-percent">{percent}%</div>
    """

def get_report_html(report_desc="영수증을 업로드하면 AI 소비 분석이 시작됩니다."):
    return f"""
    <div class="welcome-text">👋 안녕하세요</div>
    <div class="report-card">
        <div class="report-title">🤖 AI 소비 리포트</div>
        <div class="report-desc">{report_desc}</div>
    </div>
    """

def process_receipt(image, current_df, total_spent, category_data):
    if image is None:
        return current_df, get_budget_html(total_spent), category_data, get_report_html(), total_spent, category_data

    try:
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        byte_im = buf.getvalue()

        files = {'file': ('image.png', byte_im, 'image/png')}
        response = requests.post(API_URL, files=files)

        if response.status_code == 200:
            data = response.json()

            new_total = total_spent + data['total_amount']
            new_category = dict(category_data)
            top_cat = data.get('top_category', '기타')
            new_category[top_cat] = new_category.get(top_cat, 0) + data['total_amount']

            most_exp = data.get('most_expensive_item', '-')
            today = date.today().strftime("%Y-%m-%d")

            new_row = pd.DataFrame([[
                today, most_exp, top_cat, f"₩{data['total_amount']:,}", "✅ 분석완료"
            ]], columns=["날짜", "가맹점명", "카테고리", "금액", "상태"])

            valid_df = current_df[current_df["날짜"] != ""]
            new_df = pd.concat([new_row, valid_df], ignore_index=True)

            report = data.get('analysis', '')
            return new_df, get_budget_html(new_total), new_category, get_report_html(report), new_total, new_category

        elif response.status_code == 429:
            detail = response.json().get('detail', 'API 한도 초과')
            msg = f"⚠️ {detail}"
        else:
            try:
                detail = response.json().get('detail', response.text)
            except Exception:
                detail = response.text or f"HTTP {response.status_code} 오류"
            msg = f"❌ 오류 ({response.status_code}): {detail}"

    except requests.exceptions.ConnectionError:
        msg = "❌ 연결 오류: 백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요."
    except requests.exceptions.Timeout:
        msg = "❌ 시간 초과: 서버 응답이 너무 오래 걸립니다. 다시 시도해주세요."
    except Exception as e:
        msg = f"❌ 예기치 않은 오류: {str(e)}"

    return current_df, get_budget_html(total_spent), category_data, get_report_html(msg), total_spent, category_data


with gr.Blocks() as demo:
    total_spent_state = gr.State(0)
    category_state = gr.State({})

    with gr.Column(elem_classes="container"):

        # 1. Navbar
        gr.HTML("""
        <div class="navbar">
            <div class="nav-logo">🧾 영수증 AI</div>
            <div class="nav-menu">
                <span class="active">🏠 홈</span>
                <span>📁 영수증보관함</span>
            </div>
            <div class="nav-user"></div>
        </div>
        """)

        # 2. Welcome + AI Report (dynamic)
        report_html = gr.HTML(get_report_html())

        # 3. Budget & Category Row
        with gr.Row(equal_height=True):
            with gr.Column(scale=1, elem_classes="dashboard-card"):
                gr.HTML("<div class='card-title'>📊 이달의 누적 지출</div>")
                budget_viewer = gr.HTML(get_budget_html())

            with gr.Column(scale=1, elem_classes="dashboard-card"):
                gr.HTML("<div class='card-title'>🍩 카테고리별 소비 비율</div>")
                category_label = gr.Label(value={}, show_label=False)

        # 4. Receipt Table
        with gr.Column(elem_classes="dashboard-card"):
            with gr.Row(elem_classes="table-header-flex"):
                gr.Markdown("### 📸 최근 업로드한 영수증 내역")
                upload_btn = gr.Button("+ 새 영수증 올리기", variant="primary", scale=0)

            receipt_table = gr.Dataframe(
                value=initial_data,
                interactive=False,
                datatype=["str", "str", "str", "str", "str"],
                col_count=(5, "fixed")
            )

            hidden_img = gr.Image(type="pil", visible=False)
            upload_btn.click(fn=None, inputs=None, outputs=hidden_img)

    hidden_img.change(
        fn=process_receipt,
        inputs=[hidden_img, receipt_table, total_spent_state, category_state],
        outputs=[receipt_table, budget_viewer, category_label, report_html, total_spent_state, category_state]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=gr.themes.Soft(),
        css=custom_css
    )
