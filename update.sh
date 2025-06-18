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
    local timestamp
    local backup_file
    
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_file="$HOME/.hydroedit.py.bak.$timestamp"
    cp "$HOME/.hydroedit.py" "$backup_file"
    echo "$backup_file"
}

# Função para limpar backups antigos (mantém apenas os 5 mais recentes)
cleanup_old_backups() {
    local backup_dir="$HOME"
    local backup_pattern=".hydroedit.py.bak.*"
    
    # Lista todos os backups, ordena por data (mais recentes primeiro) e remove os mais antigos
    ls -t "$backup_dir"/$backup_pattern 2>/dev/null | tail -n +6 | xargs -r rm
}

# Função principal
main() {
    show_banner
    info_msg "Iniciando atualização do HydroEdit..."
    
    # Verifica se o arquivo existe
    if [ ! -f "$HOME/.hydroedit.py" ]; then
        error_msg "HydroEdit não está instalado. Por favor, execute o script de instalação primeiro."
        exit 1
    fi
    
    # Faz backup do arquivo atual com timestamp
    info_msg "Fazendo backup do arquivo atual..."
    backup_file=$(create_backup)
    
    # Baixa a nova versão
    info_msg "Baixando a nova versão..."
       if wget https://raw.githubusercontent.com/Henriquehnnm/HydroEdit/main/hydroedit.py -O "$HOME/.hydroedit.py"; then
        chmod +x "$HOME/.hydroedit.py"
        success_msg "HydroEdit atualizado com sucesso!"
        info_msg "Um backup do arquivo anterior foi salvo em: $backup_file"
        
        # Limpa backups antigos
        cleanup_old_backups
    else
        error_msg "Falha ao baixar a nova versão. Restaurando backup..."
        mv "$backup_file" "$HOME/.hydroedit.py"
        exit 1
    fi
}

# Executa a função principal
main 