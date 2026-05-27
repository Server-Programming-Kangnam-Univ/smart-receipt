import gradio as gr
import pandas as pd

# 대시보드를 위한 개선된 고급 CSS
custom_css = """
body { background-color: #f4f6f9 !important; }
.container { max-width: 1100px; margin: 0 auto; padding: 20px 15px; }

/* 상단 내비게이션 바 */
.navbar {
    display: flex; justify-content: space-between; align-items: center;
    background: white; padding: 15px 30px; border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 25px;
}
.nav-logo { font-size: 1.3rem; font-weight: 800; color: #1e293b; display: flex; align-items: center; gap: 8px; }
.nav-menu { display: flex; gap: 25px; font-weight: 600; color: #64748b; }
.nav-menu .active { color: #3b82f6; border-bottom: 2px solid #3b82f6; padding-bottom: 2px; }
.nav-user { display: flex; align-items: center; gap: 8px; font-weight: 600; color: #1e293b; }

/* 환영 문구 및 리포트 */
.welcome-text { font-size: 1.6rem; font-weight: 700; color: #0f172a; margin-bottom: 15px; }
.report-card {
    background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px;
    padding: 16px 20px; margin-bottom: 25px;
}
.report-title { font-weight: 700; color: #1e40af; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
.report-desc { color: #1e3a8a; font-size: 1.05rem; }

/* 공통 카드 스타일 */
.dashboard-card {
    background: white !important; border-radius: 16px !important; padding: 24px !important;
    border: 1px solid #e2e8f0 !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.01) !important;
    height: 100%;
    margin-bottom: 20px !important; 
}
.card-title { font-size: 1.1rem; font-weight: 700; color: #1e293b; margin-bottom: 15px; display: flex; align-items: center; gap: 6px; }

/* 누적 지출 프로그레스 바 */
.budget-amount { font-size: 1.6rem; font-weight: 800; color: #1e293b; margin-bottom: 12px; }
.budget-amount span { font-size: 1rem; color: #94a3b8; font-weight: 500; }
.progress-container { background: #e2e8f0; border-radius: 9999px; height: 12px; width: 100%; position: relative; margin-bottom: 8px; }
.progress-bar { background: #3b82f6; height: 100%; border-radius: 9999px; transition: width 0.3s ease; }
.progress-percent { text-align: right; font-size: 0.9rem; font-weight: 700; color: #64748b; }

/* 테이블 상단 바 구조 */
.table-header-flex { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.table-header-flex h3 { margin: 0 !important; }
"""

initial_data = pd.DataFrame([
    ["", "", "", "₩", ""],
    ["", "", "", "₩", ""]
], columns=["날짜", "가맹점명", "카테고리", "금액", "상태"])

with gr.Blocks() as demo:
    
    with gr.Column(elem_classes="container"):
        
        # 1. Top Navigation Bar
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
        
        # 2. Welcome Message & AI Report
        gr.HTML("""
        <div class="welcome-text">👋 안녕하세요, ~님</div>
        <div class="report-card">
            <div class="report-title">🤖 AI 소비 리포트</div>
            <div class="report-desc">"소비패턴 분석 후 추천 문구 "</div>
        </div>
        """)
        
        # 3. Middle Grid: 누적 지출 & 카테고리 소비 비율
  # 3. Middle Grid: 누적 지출 & 카테고리 소비 비율
        with gr.Row(equal_height=True):
            
            with gr.Column(scale=1, elem_classes="dashboard-card"):
                gr.HTML("<div class='card-title'>📊 이달의 누적 지출</div>")
                
                def get_budget_html(spent=300000, total=10000000):
                    if total == 0:
                        percent = 0
                    else:
                        percent = int((spent / total) * 100)
                        
                    return f"""
                    <div class="budget-amount">₩{spent:,} <span>/ 예산 ₩{total:,}</span></div>
                    <div class="progress-container">
                        <div class="progress-bar" style="width: {percent}%;"></div>
                    </div>
                    <div class="progress-percent">{percent}%</div>
                    """
                
                budget_viewer = gr.HTML(get_budget_html()) # 기본값 0, 0으로 안전하게 시작!
                
            with gr.Column(scale=1, elem_classes="dashboard-card"):
                gr.HTML("<div class='card-title'>🍩 카테고리별 소비 비율</div>")
                gr.Label(
                    value={"식비":0.5 , "Shopping": 0.2, "기타": 0.1, "교통비":0.4},
                    show_label=False
                )
        # 4. Bottom Row: 최근 업로드한 영수증 내역
        with gr.Column(elem_classes="dashboard-card"):
            with gr.Row(elem_classes="table-header-flex"):
                gr.Markdown("### 📸 최근 업로드한 영수증 내역")
                upload_btn = gr.Button("+ 새 영수증 올리기", variant="primary", scale=0)
                
            # 💡 에러를 유발하는 변수(stretch, container)를 모두 없애고 완벽한 공통 옵션만 남겼습니다.
            receipt_table = gr.Dataframe(
                value=initial_data,
                interactive=False,
                datatype=["str", "str", "str", "str", "str"],
                col_count=(5, "fixed")
            )
            
            hidden_img = gr.Image(type="pil", visible=False)
            upload_btn.click(fn=None, inputs=None, outputs=hidden_img)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0", 
        server_port=7860, 
        theme=gr.themes.Soft(), 
        css=custom_css
    )