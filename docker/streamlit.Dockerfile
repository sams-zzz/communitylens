FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "streamlit>=1.40,<2" "plotly>=5.24,<7" "pandas>=2.2,<4" "requests>=2.32,<3"
COPY streamlit_app ./streamlit_app
RUN useradd --create-home app
USER app
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
