#!/bin/bash

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Função para exibir banner
show_banner() {
    echo -e "${CYAN}"
    echo "╭──────────────────────────────────────────────────────────╮"
    echo "│                     HydroEdit Installer                  │"
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

# Função para exibir mensagem de aviso
warning_msg() {
    echo -e "${YELLOW}╭── $1${NC}"
    echo -e "${YELLOW}╰──>${NC}"
}

# Função para exibir progresso
progress_msg() {
    echo -e "${MAGENTA}╭── $1${NC}"
    echo -e "${MAGENTA}╰──>${NC}"
}

# Função para detectar o sistema operacional
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            echo "debian"
        elif [ -f /etc/redhat-release ]; then
            echo "redhat"
        elif [ -f /etc/arch-release ]; then
            echo "arch"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

# Função para instalar dependências
install_dependencies() {
    local os_type=$1
    progress_msg "Instalando dependências do sistema..."
    
    case $os_type in
        "debian"|"ubuntu")
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv python3-full
            # Criar ambiente virtual
            progress_msg "Criando ambiente virtual Python..."
            python3 -m venv ~/.hydroedit-venv
            source ~/.hydroedit-venv/bin/activate
            progress_msg "Instalando pacotes Python..."
            pip install autopep8 jsbeautifier
            deactivate
            ;;
        "redhat"|"fedora"|"centos")
            sudo dnf install -y python3 python3-pip python3-virtualenv
            progress_msg "Criando ambiente virtual Python..."
            python3 -m venv ~/.hydroedit-venv
            source ~/.hydroedit-venv/bin/activate
            progress_msg "Instalando pacotes Python..."
            pip install autopep8 jsbeautifier
            deactivate
            ;;
        "arch")
            sudo pacman -S --noconfirm python python-pip python-virtualenv
            progress_msg "Criando ambiente virtual Python..."
            python -m venv ~/.hydroedit-venv
            source ~/.hydroedit-venv/bin/activate
            progress_msg "Instalando pacotes Python..."
            pip install autopep8 jsbeautifier
            deactivate
            ;;
        "macos")
            brew install python3
            progress_msg "Criando ambiente virtual Python..."
            python3 -m venv ~/.hydroedit-venv
            source ~/.hydroedit-venv/bin/activate
            progress_msg "Instalando pacotes Python..."
            pip install autopep8 jsbeautifier
            deactivate
            ;;
        *)
            error_msg "Sistema operacional não suportado"
            exit 1
            ;;
    esac
}

# Função para configurar aliases
setup_aliases() {
    local shell_type=$1
    local editor_path="~/.hydroedit.py"
    local venv_path="~/.hydroedit-venv/bin/python"
    
    progress_msg "Configurando aliases para o shell $shell_type..."
    
    case $shell_type in
        "bash")
            echo "" >> ~/.bashrc
            echo "# HydroEdit aliases" >> ~/.bashrc
            echo "alias hydroedit='$venv_path $editor_path'" >> ~/.bashrc
            echo "alias he='$venv_path $editor_path'" >> ~/.bashrc
            ;;
        "zsh")
            echo "" >> ~/.zshrc
            echo "# HydroEdit aliases" >> ~/.zshrc
            echo "alias hydroedit='$venv_path $editor_path'" >> ~/.zshrc
            echo "alias he='$venv_path $editor_path'" >> ~/.zshrc
            ;;
        "fish")
            echo "" >> ~/.config/fish/config.fish
            echo "# HydroEdit aliases" >> ~/.config/fish/config.fish
            echo "alias hydroedit='$venv_path $editor_path'" >> ~/.config/fish/config.fish
            echo "alias he='$venv_path $editor_path'" >> ~/.config/fish/config.fish
            ;;
    esac
}

# Função principal
main() {
    show_banner
    info_msg "Iniciando instalação do HydroEdit..."
    
    # Detecta o sistema operacional
    os_type=$(detect_os)
    info_msg "Sistema operacional detectado: ${BOLD}$os_type${NC}"
    
    # Instala dependências
    install_dependencies $os_type
    
    # Copia o editor para a home
    progress_msg "Copiando o editor para $HOME/.hydroedit.py"
    cp hydroedit.py "$HOME/.hydroedit.py"
    chmod +x "$HOME/.hydroedit.py"
    
    # Detecta o shell atual
    current_shell=$(basename "$SHELL")
    info_msg "Shell detectado: ${BOLD}$current_shell${NC}"
    
    # Configura aliases
    setup_aliases $current_shell
    
    echo -e "\n${GREEN}╭──────────────────────────────────────────────────────────╮"
    echo -e "│                    Instalação Concluída!                 │"
    echo -e "╰──────────────────────────────────────────────────────────╯${NC}\n"
    
    info_msg "Você pode usar o editor com os comandos:"
    echo -e "  ${BOLD}hydroedit <arquivo>${NC}"
    echo -e "  ${BOLD}he <arquivo>${NC}"
    
    warning_msg "Reinicie seu terminal e comece a usar o HydroEdit!"
}

# Executa a função principal
main 