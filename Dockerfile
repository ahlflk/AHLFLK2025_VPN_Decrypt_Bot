FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render Port (Webhook အတွက် 8080 က အိုကေပါတယ်)
ENV PORT=8080

# bot.py ထဲက app (Flask) ကို gunicorn နဲ့ ချိတ်ပတ်ပြီး run ခိုင်းတာဖြစ်ပါတယ်
CMD ["gunicorn", "-b", "0.0.0.0:8080", "bot:app"]
