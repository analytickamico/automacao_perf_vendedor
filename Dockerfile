FROM python:3.10-slim
WORKDIR /app

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    unzip \
    awscli \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf aws awscliv2.zip

# Copiar o código da aplicação
COPY . .

# Expor as portas do Streamlit
EXPOSE 8501 8504

# Script de inicialização
RUN echo '#!/bin/bash\n\
streamlit run 1_🏠_home.py --server.port 8501 & \n\
streamlit run monitor_pedidos.py --server.port 8504 & \n\
wait' > /app/start.sh && \
chmod +x /app/start.sh

# Comando para iniciar a aplicação
CMD ["/app/start.sh"]