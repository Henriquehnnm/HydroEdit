#!/bin/bash

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Função para exibir banner
show_banner() {
    echo -e "${CYAN}"
    echo "╭──────────────────────────────────────────────────────────╮"
    echo "│                     HydroEdit Updater                    │"
    echo "╰──────────────────────────────────────────────────────────╯"
    echo -e "${NC}"
}

# Função para exibir mensagem de sucesso
success_msg() {
    echo -e "${GREEN}╭── $1${NC}"
    echo -e "${GREEN}╰──>${NC}"
}

# Função para exibir mensagem de erro
error_msg() {
    echo -e "${RED}╭── $1${NC}"
    echo -e "${RED}╰──>${NC}"
}

# Função para exibir mensagem de informação
info_msg() {
    echo -e "${BLUE}╭── $1${NC}"
    echo -e "${BLUE}╰──>${NC}"
}

# Função para criar backup com timestamp
create_backup() {
    :
}

# Função para limpar backups antigos (mantém apenas os 5 mais recentes)
cleanup_old_backups() {
    :
}

# Função principal
main() {
    show_banner
    info_msg "Iniciando atualização do HydroEdit..."
    
    # Verifica se o wget está instalado
    if ! command -v wget >/dev/null 2>&1; then
        error_msg "O comando 'wget' não está instalado. Instale-o para continuar."
        exit 1
    fi
    
    # Verifica se o arquivo existe
    if [ ! -f "$HOME/.hydroedit.py" ]; then
        error_msg "HydroEdit não está instalado. Por favor, execute o script de instalação primeiro."
        exit 1
    fi
    
    # Baixa a nova versão para um arquivo temporário
    info_msg "Baixando a nova versão..."
    temp_file=$(mktemp)
    if wget https://raw.githubusercontent.com/Henriquehnnm/HydroEdit/main/hydroedit.py -O "$temp_file"; then
        info_msg "Removendo a versão antiga..."
        rm -f "$HOME/.hydroedit.py"
        mv "$temp_file" "$HOME/.hydroedit.py"
        chmod +x "$HOME/.hydroedit.py"
        success_msg "HydroEdit atualizado com sucesso!"
    else
        error_msg "Falha ao baixar a nova versão. Nenhuma alteração foi feita."
        rm -f "$temp_file"
        exit 1
    fi
}

# Executa a função principal
main 