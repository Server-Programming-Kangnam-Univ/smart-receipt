import gradio as gr
import requests
import pandas as pd
import io
from PIL import Image

# Backend API URL
API_URL = "http://localhost:8000/analyze-receipt/"

# Custom CSS for modern look
custom_css = """
.container { max-width: 1200px; margin: auto; padding-top: 20px; }
.header { text-align: center; margin-bottom: 30px; }
.card { 
    background: white; 
    border-radius: 10px; 
    padding: 20px; 
    box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
    margin-bottom: 20px;
}
.summary-card {
    background: #f8f9fa;
    border-left: 5px solid #007bff;
    padding: 15px;
    border-radius: 5px;
    text-align: center;
}
.summary-value {
    font-size: 1.5em;
    font-weight: bold;
    color: #007bff;
}
.summary-label {
    font-size: 0.9em;
    color: #6c757d;
}
"""

def analyze_receipt_ui(image):
    if image is None:
        return [None] * 5

    try:
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        byte_im = buf.getvalue()

        files = {'file': ('image.png', byte_im, 'image/png')}
        response = requests.post(API_URL, files=files)
        
        if response.status_code == 200:
            data = response.json()
            items_df = pd.DataFrame(data['items'])
            items_df.columns = ['품목명', '가격', '수량', '카테고리']

            total_str = f"{data['total_amount']:,}원"
            top_cat = data.get('top_category', 'N/A')
            most_exp = data.get('most_expensive_item', 'N/A')
            analysis_text = data['analysis']

            return total_str, top_cat, most_exp, items_df, analysis_text
        elif response.status_code == 429:
            detail = response.json().get('detail', 'API 한도 초과')
            return "한도 초과", "-", "-", None, f"⚠️ {detail}"
        else:
            detail = response.json().get('detail', response.text)
            return "오류", "오류", "오류", None, f"❌ {detail}"

    except Exception as e:
        return "Error", "Error", "Error", None, str(e)

# Gradio Interface
with gr.Blocks() as demo:
    # Use gr.Column instead of gr.Div for broader compatibility
    with gr.Column(elem_classes="container"):
        # Header
        gr.Markdown("# 🧾 영수증 AI 소비 분석 서비스", elem_classes="header")
        gr.Markdown("영수증 사진을 찍어 올리시면 AI가 소비 내역을 분석해드립니다.", elem_classes="header")
        
        with gr.Row():
            # Left: Input
            with gr.Column(scale=1):
                with gr.Column(elem_classes="card"):
                    gr.Markdown("### 📸 영수증 업로드")
                    input_image = gr.Image(type="pil", label=None)
                    with gr.Row():
                        clear_btn = gr.Button("초기화")
                        submit_btn = gr.Button("분석 시작", variant="primary")
            
            # Right: Results
            with gr.Column(scale=2):
                with gr.Column(elem_classes="card"):
                    gr.Markdown("### 📊 분석 요약")
                    with gr.Row():
                        with gr.Column(elem_classes="summary-card"):
                            gr.Markdown("<div class='summary-label'>총 지출 금액</div>")
                            total_output = gr.Markdown("<div class='summary-value'>-</div>")
                        with gr.Column(elem_classes="summary-card"):
                            gr.Markdown("<div class='summary-label'>주요 카테고리</div>")
                            top_cat_output = gr.Markdown("<div class='summary-value'>-</div>")
                        with gr.Column(elem_classes="summary-card"):
                            gr.Markdown("<div class='summary-label'>가장 비싼 품목</div>")
                            most_exp_output = gr.Markdown("<div class='summary-value'>-</div>")
                
                with gr.Column(elem_classes="card"):
                    gr.Markdown("### 🛒 상세 구매 내역")
                    output_df = gr.Dataframe(label=None, interactive=False)
                
                with gr.Column(elem_classes="card"):
                    gr.Markdown("### 💡 AI 분석 인사이트")
                    analysis_output = gr.Textbox(label=None, placeholder="분석 결과가 여기에 표시됩니다.", lines=4, interactive=False)

    # Event handlers
    def update_outputs(total, top, most, df, analysis):
        return (
            f"<div class='summary-value'>{total}</div>",
            f"<div class='summary-value'>{top}</div>",
            f"<div class='summary-value'>{most}</div>",
            df,
            analysis
        )

    def process_and_update(image):
        res = analyze_receipt_ui(image)
        return update_outputs(*res)

    submit_btn.click(
        fn=process_and_update,
        inputs=input_image,
        outputs=[total_output, top_cat_output, most_exp_output, output_df, analysis_output]
    )
    
    clear_btn.click(
        fn=lambda: (None, "<div class='summary-value'>-</div>", "<div class='summary-value'>-</div>", "<div class='summary-value'>-</div>", None, ""),
        inputs=None,
        outputs=[input_image, total_output, top_cat_output, most_exp_output, output_df, analysis_output]
    )

if __name__ == "__main__":
    # Move css parameter to launch() as suggested by Gradio 6.0 warning
    demo.launch(server_name="0.0.0.0", server_port=7860, css=custom_css)
