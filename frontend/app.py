# -*- coding: utf-8 -*-
import gradio as gr
import requests
import pandas as pd
from datetime import datetime
import calendar
import json
import os
import plotly.express as px

# API 주소 설정
BASE_URL = "http://127.0.0.1:8000"
API_URL = f"{BASE_URL}/analyze-receipt/"
SAVE_URL = f"{BASE_URL}/save-receipt/"
SAVE_BULK_URL = f"{BASE_URL}/save-receipts-bulk/"
HISTORY_URL = f"{BASE_URL}/history/"
ASK_AI_URL = f"{BASE_URL}/ask-ai/"
BUDGET_URL = f"{BASE_URL}/budget/"

# [채상원 기여] Custom CSS
custom_css = """
body { background-color: #f8fafc !important; }
.container { max-width: 800px; margin: 0 auto; padding: 20px; }
.card { 
    background: white; border-radius: 12px; padding: 30px; 
    border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); 
    margin-bottom: 20px;
}
"""

def safe_api(method, url, **kwargs):
    try:
        res = requests.request(method, url, timeout=5, **kwargs)
        return res.json() if res.status_code == 200 else None
    except: return None

def generate_pie_chart(cats):
    if not cats:
        return None
    
    df = pd.DataFrame(list(cats.items()), columns=['Category', 'Amount'])
    # Plotly 원 그래프 생성
    fig = px.pie(df, values='Amount', names='Category', hole=0.3,
                 color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
    return fig

def refresh_basic_info():
    history = safe_api("GET", HISTORY_URL) or []
    budget_data = safe_api("GET", BUDGET_URL) or {"budget": 1000000}
    budget = budget_data.get("budget", 1000000)
    
    total = sum(r.get('total_amount', 0) for r in history)
    
    # 카테고리별 지출 데이터 계산
    cats = {}
    for r in history:
        c = r.get('top_category', '기타')
        cats[c] = cats.get(c, 0) + r.get('total_amount', 0)
        
    now = datetime.now()
    _, last = calendar.monthrange(now.year, now.month)
    days = max(1, last - now.day + 1)
    daily = max(0, (budget - total) // days)
    
    percent = min(int((total / budget) * 100), 100) if budget > 0 else 0
    color = "#3b82f6" if percent < 80 else "#ef4444"
    
    spending_html = f"""
    <div class='card'>
        <div style='font-size: 1.2em; color: #64748b; margin-bottom: 10px; font-weight: 600;'>이번 달 총 지출</div>
        <div style='font-size: 2.5em; font-weight: 800; color: #1e293b;'>₩{total:,} <span style='font-size: 0.4em; color: #94a3b8;'>/ 목표 ₩{budget:,}</span></div>
        <div style='background: #e2e8f0; height: 16px; border-radius: 8px; margin: 20px 0;'>
            <div style='background: {color}; width: {percent}%; height: 100%; border-radius: 8px; transition: width 0.8s;'></div>
        </div>
        <div style='display: flex; justify-content: space-between; font-size: 1.1em; font-weight: 700;'>
            <span style='color: #64748b;'>{percent}% 사용됨</span>
            <span style='color: #059669;'>📅 오늘 권장 지출액: ₩{daily:,}</span>
        </div>
    </div>
    """
    
    table_data = [[r.get('date'), r.get('top_category', '기타'), r.get('store_name'), r.get('total_amount',0)] for r in history]
    table_df = pd.DataFrame(table_data, columns=["날짜", "카테고리", "장소", "금액"])
    
    pie_chart = generate_pie_chart(cats)
    
    return spending_html, table_df, pie_chart

def start_analysis(img):
    """
    무한 로딩(Hanging)을 방지하기 위해 gr.update(value=...)를 쓰지 않고 
    직접 None을 반환하여 완벽한 '공란'을 만듭니다.
    반환 순서: edit_area(update), date(raw), category(raw), place(raw), amount(raw), status_msg(raw), save_btn(update)
    """
    if not img: 
        return gr.update(visible=False), None, "기타", None, None, "❌ 파일을 업로드하세요.", gr.update(visible=False)
    
    try:
        res = requests.post(API_URL, files={'file': open(img, 'rb')}, timeout=120)
        
        if res.status_code != 200:
            err_msg = f"❌ AI 분석 실패 (모든 항목을 직접 입력해주세요): HTTP {res.status_code}"
            return gr.update(visible=True), None, "기타", None, None, err_msg, gr.update(visible=True)
            
        data = res.json()
        
        raw_date = str(data.get("date", "")).strip()
        raw_place = str(data.get("store_name", "")).strip()
        raw_cat = str(data.get("top_category", "기타")).strip()
        
        # 1. 금액 파싱
        amt_value = None
        try:
            parsed_amt = int(data.get("total_amount", 0))
            if parsed_amt > 0:
                amt_value = parsed_amt
        except:
            pass
            
        missing_fields = []
        
        # 2. 날짜 누락 검증 -> 누락 시 완벽한 공란(None)
        if not raw_date or raw_date.lower() in ["none", "null"] or "오늘" in raw_date:
            date_str = None
            missing_fields.append("날짜")
        else:
            date_str = raw_date
            
        # 3. 장소 누락 검증 -> 누락 시 완벽한 공란(None)
        if not raw_place or raw_place.lower() in ["none", "null"] or "알 수 없" in raw_place:
            place_str = None
            missing_fields.append("장소")
        else:
            place_str = raw_place
            
        # 4. 카테고리 검증
        VALID_CATS = ["식비", "교통", "쇼핑", "문화", "의료", "기타"]
        cat_str = raw_cat if raw_cat in VALID_CATS else "기타"
            
        # 5. 금액 누락 검증
        if amt_value is None or amt_value <= 0:
            amt_value = None
            if "금액" not in missing_fields:
                missing_fields.append("금액")
            
        # 6. 메시지 구성
        if missing_fields:
            status_message = f"⚠️ 분석 완료 (누락 발견: {', '.join(missing_fields)}). 비어있는 칸을 직접 입력해 주세요."
        else:
            status_message = "✅ 분석 완료! 내용을 확인하고 수정 후 저장하세요."
            
        return gr.update(visible=True), date_str, cat_str, place_str, amt_value, status_message, gr.update(visible=True)
        
    except Exception as e: 
        err_msg = f"❌ 서버 연결 오류 (모든 항목을 직접 입력해주세요)"
        return gr.update(visible=True), None, "기타", None, None, err_msg, gr.update(visible=True)


def finalize_save(date, category, place, amount, img):
    """
    공란(None) 상태로 넘어온 데이터를 안전하게 처리하여 서버에 저장합니다.
    """
    try:
        # 공란 방어 로직 (빈칸이면 0 또는 기본 문구로 처리)
        safe_date = str(date).strip() if date else datetime.now().strftime("%Y-%m-%d")
        safe_place = str(place).strip() if place else "미입력 장소"
        
        try: safe_amount = int(amount)
        except: safe_amount = 0
        
        safe_cat = str(category).strip() if category else "기타"

        data = {
            "date": safe_date,
            "store_name": safe_place,
            "total_amount": safe_amount,
            "items": [],
            "top_category": safe_cat
        }
        requests.post(SAVE_URL, data={'data': json.dumps(data, ensure_ascii=False)}, files={'file': open(img, 'rb')}, timeout=10)
        return "✅ 성공적으로 저장되었습니다!"
    except Exception as e: 
        return f"❌ 저장에 실패했습니다: {str(e)}"


def chat_with_ai(msg, hist):
    if not msg: return "", hist
    try:
        res = requests.post(ASK_AI_URL, json={"question": msg}, timeout=20).json()
        ans = res.get("answer", "오류가 발생했습니다.")
    except: ans = "서버에 연결할 수 없습니다."
    hist.append((msg, ans))
    return "", hist

with gr.Blocks(title="스마트 영수증 비서", css=custom_css, theme=gr.themes.Soft()) as demo:
    with gr.Column(elem_classes="container"):
        gr.HTML("<h1 style='text-align: center; color: #0f172a; padding: 20px;'>🧾 스마트 영수증 비서</h1>")
        
        with gr.Tabs():
            # 1. 지출 현황
            with gr.Tab("📊 지출 현황"):
                spending_display = gr.HTML("데이터를 불러오는 중...")
                with gr.Accordion("⚙️ 목표 지출 금액 설정", open=False):
                    budget_in = gr.Number(label="한 달 목표 지출 금액 (원)", value=1000000)
                    budget_save = gr.Button("저장하기")

            # 2. 소비 분석 (AI 챗봇 + 차트)
            with gr.Tab("🤖 소비 분석"):
                gr.Markdown("### 🍕 카테고리별 지출 비중")
                cat_chart = gr.Plot(show_label=False)
                chatbot = gr.Chatbot(height=400)
                with gr.Row():
                    chat_input = gr.Textbox(placeholder="질문을 입력하세요...", scale=9, show_label=False)
                    send_btn = gr.Button("전송")

            # 3. 영수증 올리기
            with gr.Tab("📸 영수증 올리기"):
                with gr.Row():
                    with gr.Column():
                        img_input = gr.Image(type="filepath", label="영수증 이미지 업로드")
                        ana_btn = gr.Button("🔍 AI 분석 시작", variant="primary")
                        status_msg = gr.Markdown("영수증 이미지를 선택하세요.")
                    with gr.Column(visible=False) as edit_area:
                        gr.Markdown("### 📝 결과 확인 및 수정")
                        with gr.Row():
                            edit_date = gr.Textbox(label="결제 날짜", placeholder="YYYY-MM-DD")
                            edit_category = gr.Dropdown(choices=["식비", "교통", "쇼핑", "문화", "의료", "기타"], label="카테고리")
                            edit_place = gr.Textbox(label="방문 장소", placeholder="가맹점 또는 상호명")
                            edit_amount = gr.Number(label="결제 금액 (원)", precision=0)
                        save_btn = gr.Button("💾 최종 저장하기", variant="secondary")

            # 4. CSV 업로드
            with gr.Tab("📁 CSV 업로드"):
                gr.Markdown("### 엑셀(CSV) 파일로 지출 내역 한 번에 올리기")
                with gr.Row():
                    with gr.Column():
                        csv_upload = gr.File(label="CSV 파일 업로드", file_types=[".csv"])
                        csv_ana_btn = gr.Button("🔍 CSV AI 분석 및 자동 저장", variant="primary")
                        csv_status = gr.Markdown("파일을 올리고 버튼을 누르세요. 분석 완료 시 자동으로 보관함에 저장됩니다.")
                    with gr.Column(visible=False) as csv_review_area:
                        csv_preview = gr.Dataframe(
                            headers=["날짜", "카테고리", "장소", "금액"], 
                            column_count=(4, "fixed"), 
                            interactive=False, # 자동 저장되므로 읽기 전용으로 변경
                            label="서버에 자동 저장된 데이터"
                        )

            # 5. 보관함
            with gr.Tab("📁 보관함"):
                with gr.Row():
                    refresh_btn = gr.Button("🔄 새로고침")
                    clear_btn = gr.Button("🗑️ 전체 삭제", variant="stop")
                gr.Markdown("*(셀 더블클릭으로 수정 가능. 카테고리는 [식비, 교통, 쇼핑, 문화, 의료, 기타] 중 하나로 입력해야 자동 변환됩니다.)*")
                history_table = gr.Dataframe(interactive=True)
                history_save_btn = gr.Button("💾 수정된 표 전체 저장하기", variant="primary")
                history_status = gr.Markdown()

    def update_all():
        return refresh_basic_info()

    demo.load(update_all, None, [spending_display, history_table, cat_chart])

    budget_save.click(lambda v: requests.post(BUDGET_URL, json={"budget": int(v)}), [budget_in], None).then(
        update_all, None, [spending_display, history_table, cat_chart]
    )

    ana_btn.click(
        start_analysis, 
        [img_input], 
        [edit_area, edit_date, edit_category, edit_place, edit_amount, status_msg, save_btn]
    )
    
    save_btn.click(
        finalize_save, 
        [edit_date, edit_category, edit_place, edit_amount, img_input], 
        [status_msg]
    ).then(
        update_all, None, [spending_display, history_table, cat_chart]
    ).then(
        lambda: gr.update(visible=False), None, edit_area
    )

    refresh_btn.click(update_all, None, [spending_display, history_table, cat_chart])
    clear_btn.click(lambda: requests.delete(HISTORY_URL), None, None).then(
        update_all, None, [spending_display, history_table, cat_chart]
    )

    def process_and_save_csv(file):
        if not file:
            return gr.update(visible=False), pd.DataFrame(), "❌ 파일을 업로드하세요."
        try:
            # 1. AI 분석 요청
            res = requests.post(f"{BASE_URL}/analyze-csv/", files={'file': open(file.name, 'rb')}, timeout=120)
            if res.status_code != 200:
                return gr.update(visible=False), pd.DataFrame(), f"❌ 분석 실패: HTTP {res.status_code}"
            
            data = res.json()
            table_data = []
            payload = []
            VALID_CATS = ["식비", "교통", "쇼핑", "문화", "의료", "기타"]
            
            # 2. 데이터 가공 및 저장용 Payload 생성
            for r in data:
                amt = int(r.get('total_amount', 0))
                cat = str(r.get('top_category', '기타'))
                cat = cat if cat in VALID_CATS else "기타"
                date_str = str(r.get('date', ''))
                place_str = str(r.get('store_name', ''))
                
                table_data.append([date_str, cat, place_str, amt])
                payload.append({
                    "date": date_str,
                    "top_category": cat,
                    "store_name": place_str,
                    "total_amount": amt,
                    "items": []
                })
            
            # 3. 서버에 즉시 자동 저장
            save_res = requests.post(SAVE_BULK_URL, json=payload, timeout=10)
            if save_res.status_code != 200:
                return gr.update(visible=False), pd.DataFrame(), f"❌ 자동 저장 실패: HTTP {save_res.status_code}"

            df = pd.DataFrame(table_data, columns=["날짜", "카테고리", "장소", "금액"])
            return gr.update(visible=True), df, f"✅ 분석 및 보관함 자동 저장 완료! ({len(df)}건)"
            
        except Exception as e:
            return gr.update(visible=False), pd.DataFrame(), f"❌ 오류 발생: {str(e)}"

    csv_ana_btn.click(
        process_and_save_csv,
        [csv_upload],
        [csv_review_area, csv_preview, csv_status]
    ).then(
        update_all, None, [spending_display, history_table, cat_chart]
    )

    # 보관함 수동 대량 저장 로직
    def save_manual_edit(df):
        try:
            # 1. 기존 데이터 삭제
            requests.delete(HISTORY_URL, timeout=5)
            
            # 2. 수정한 표 데이터를 읽어서 payload 구성
            payload = []
            VALID_CATS = ["식비", "교통", "쇼핑", "문화", "의료", "기타"]
            for _, row in df.iterrows():
                # 통화 기호나 콤마 처리
                amt_str = str(row["금액"]).replace("₩", "").replace(",", "").strip()
                try: amt = int(amt_str)
                except: amt = 0
                
                cat_str = str(row["카테고리"])
                cat_str = cat_str if cat_str in VALID_CATS else "기타"
                
                payload.append({
                    "date": str(row["날짜"]),
                    "top_category": cat_str,
                    "store_name": str(row["장소"]),
                    "total_amount": amt,
                    "items": []
                })
            
            # 3. 역순으로 다시 밀어넣기
            res = requests.post(SAVE_BULK_URL, json=payload[::-1], timeout=10)
            if res.status_code == 200:
                return "✅ 수정된 표 전체가 성공적으로 저장되었습니다."
            else:
                return f"❌ 저장 실패: HTTP {res.status_code}"
        except Exception as e:
            return f"❌ 저장 중 오류 발생: {str(e)}"

    history_save_btn.click(
        save_manual_edit,
        [history_table],
        [history_status]
    ).then(
        update_all, None, [spending_display, history_table, cat_chart]
    )

    chat_input.submit(chat_with_ai, [chat_input, chatbot], [chat_input, chatbot])
    send_btn.click(chat_with_ai, [chat_input, chatbot], [chat_input, chatbot])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, css=custom_css, theme=gr.themes.Soft())