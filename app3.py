import streamlit as st
import requests
import base64
from pdf2image import convert_from_bytes
from io import BytesIO
import datetime
import random

# ── مفتاح DeepSeek الواحد لكل شيء ──
DEEPSEEK_API_KEY = "sk-sk-befbda345e8b4d84b0717414854a56c7"  # ← ضع مفتاحك الحقيقي هنا

# ── دالة اتصال موحدة بـ DeepSeek ──
def call_deepseek(messages, model="deepseek-chat", max_tokens=4096, temperature=0.3):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    try:
        r = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers, timeout=90)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"خطأ في DeepSeek: {str(e)}")
        return None

# ── استخراج نص من صفحة صورة (OCR) ──
def ocr_page(image_bytes):
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "استخرج كل النص العربي من هذه الصفحة بدقة عالية، مع الحفاظ على الترتيب والفقرات والعناوين والجداول إن وجدت. لا تضف أي تعليق أو تفسير خارج النص."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
        ]}
    ]
    return call_deepseek(messages, model="deepseek-vl")  # أو الاسم الدقيق لنموذج الرؤية

# ── استخراج نص من PDF كامل أو جزء منه ──
def extract_text_from_pdf(uploaded_file, max_pages=50):
    if not uploaded_file:
        return ""
    try:
        images = convert_from_bytes(uploaded_file.read(), dpi=180, first_page=1, last_page=max_pages)
        full_text = ""
        progress = st.progress(0)
        for i, img in enumerate(images):
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            page_text = ocr_page(buffered.getvalue())
            if page_text:
                full_text += f"صفحة {i+1}:\n{page_text}\n\n"
            progress.progress((i + 1) / len(images))
        return full_text.strip()
    except Exception as e:
        st.error(f"خطأ أثناء معالجة PDF: {e}")
        return ""

# ── واجهة رفع الفهرس
st.header("1. رفع فهرس الكتاب (جدول المحتويات)")
index_file = st.file_uploader("PDF لفهرس الكتاب", type="pdf", key="index_pdf")

if index_file:
    with st.spinner("جاري استخراج فهرس الكتاب..."):
        index_text = extract_text_from_pdf(index_file, max_pages=10)
        if index_text:
            st.session_state["index_text"] = index_text
            st.success("تم استخراج الفهرس")
            with st.expander("معاينة الفهرس"):
                st.text(index_text[:2000] + "..." if len(index_text) > 2000 else index_text)

            # تحليل الفهرس لاستخراج الدروس
            prompt = f"""
            اقرأ النص التالي (فهرس كتاب مدرسي سعودي) واستخرج قائمة بأسماء الفصول والدروس الرئيسية فقط.
            أعد النتيجة كقائمة مرقمة نصية فقط، بدون أي مقدمة أو شرح إضافي.

            النص:
            {index_text[:15000]}
            """
            lessons_raw = call_deepseek([{"role": "user", "content": prompt}], model="deepseek-chat")
            if lessons_raw:
                lessons = [line.strip() for line in lessons_raw.split('\n') if line.strip() and line.strip()[0].isdigit()]
                st.session_state["lessons_list"] = lessons
                st.success(f"تم استخراج {len(lessons)} فصل/درس")

# ── اختيار الدرس
lessons = st.session_state.get("lessons_list", [])
if lessons:
    selected_lesson = st.selectbox("اختر الدرس / الفصل", lessons)
else:
    selected_lesson = st.text_input("أدخل اسم الدرس يدويًا")

# ── رفع الكتاب الكامل
st.header("2. رفع الكتاب الكامل")
book_file = st.file_uploader("PDF الكتاب", type="pdf", key="book_pdf")

if book_file:
    with st.spinner("جاري استخراج نص الكتاب (قد يستغرق وقتًا)..."):
        book_text = extract_text_from_pdf(book_file)
        if book_text:
            st.session_state["book_text"] = book_text
            st.success("تم استخراج نص الكتاب")
            with st.expander("معاينة جزء من الكتاب"):
                st.text(book_text[:1500] + "...")

# ── توليد الأسئلة
if st.session_state.get("book_text") and selected_lesson:
    st.header(f"إنشاء أسئلة لـ: {selected_lesson}")

    col1, col2, col3, col4 = st.columns(4)
    n_tf   = col1.number_input("صح/خطأ", 0, 10, 4)
    n_mcq  = col2.number_input("اختياري", 0, 10, 4)
    n_essay= col3.number_input("مقالي", 0, 5, 2)
    n_fill = col4.number_input("ملء فراغات", 0, 10, 3)

    if st.button("توليد الأسئلة الآن"):
        text = st.session_state["book_text"]
        prompt = f"""
        لديك النص التالي من كتاب مدرسي سعودي (الدرس: {selected_lesson}):

        {text[:30000]}

        أنشئ أسئلة دقيقة مبنية فقط على النص أعلاه:
        - {n_tf} سؤال صح/خطأ (ابدأ كل سؤال بـ TF: )
        - {n_mcq} سؤال اختيار متعدد (ابدأ بـ MCQ: ) بصيغة: السؤال؟ || أ- .. || ب- .. || ج- .. || د- ..
        - {n_essay} سؤال مقالي مفتوح (ابدأ بـ ESSAY: )
        - {n_fill} سؤال ملء فراغ (ابدأ بـ FILL: ) باستخدام _____

        الأسئلة يجب أن تكون تعليمية ومتنوعة المستوى.
        أعد النتيجة كنصوص فقط، كل سؤال في سطر منفصل.
        """

        with st.spinner("جاري توليد الأسئلة عبر DeepSeek..."):
            result = call_deepseek([{"role": "user", "content": prompt}], model="deepseek-chat")
            if result:
                st.markdown("### الأسئلة المتولدة")
                st.markdown(f"```\n{result}\n```")
            else:
                st.error("لم يتم توليد الأسئلة، تحقق من المفتاح أو الاتصال.")
