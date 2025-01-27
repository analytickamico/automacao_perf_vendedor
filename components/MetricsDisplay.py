import streamlit as st

def create_metric_card(title, value, color):
    return f"""
        <div style="
            background-color: #F8F9FA;
            border-radius: 4px;
            padding: 16px;
            margin: 5px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        ">
            <div style="
                color: #6B7280;
                font-size: 12px;
                margin-bottom: 4px;
            ">{title}</div>
            <div style="
                color: {color};
                font-size: 16px;
                font-weight: bold;
            ">{value}</div>
        </div>
    """

def MetricsDisplay(faturamentoTotal, valorEstoque, totalSkus, giroEstoque, curvaA, curvaB, curvaC):
    st.markdown(
        f"""
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-bottom: 15px;">
            {create_metric_card("Faturamento Total", faturamentoTotal, "#3B82F6")}
            {create_metric_card("Valor Total em Estoque", valorEstoque, "#10B981")}
            {create_metric_card("Total de SKUs", totalSkus, "#8B5CF6")}
        </div>       
        """,
        unsafe_allow_html=True
    )