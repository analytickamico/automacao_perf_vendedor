import streamlit as st
from PIL import Image
import os

def convert_to_favicon(jpg_path, output_dir):
    """
    Converte um arquivo JPG para ICO e PNG e retorna o caminho do arquivo ICO.
    """
    img = Image.open(jpg_path)
    
    # Redimensionar para tamanhos comuns de favicon
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    img.save(os.path.join(output_dir, "favicon.png"), sizes=sizes)
    
    # Converter para ICO
    ico_path = os.path.join(output_dir, "favicon.ico")
    img.save(ico_path, format='ICO', sizes=sizes)
    
    return ico_path

# Caminhos dos arquivos
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
jpg_path = os.path.join(current_dir, "kamicogroup_logo.jpg")
output_dir = parent_dir

# Converter e obter o caminho do favicon
favicon_path = convert_to_favicon(jpg_path, current_dir)



