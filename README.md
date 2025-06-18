  <p class="center">
    <img src="https://capsule-render.vercel.app/api?type=waving&color=8BE9FD&height=220&section=header&text=HydroEdit&fontSize=40&fontColor=F8F8F2" alt="HydroEdit Header" />
  </p>

HydroEdit é um editor de texto para terminal, escrito em Python, que oferece uma experiência de edição moderna com suporte a realce de sintaxe, busca avançada e formatação de código, utilizando uma interface TUI (Text User Interface) estilizada com `curses`.

## Funcionalidades

* Editor de texto completo com suporte a múltiplos arquivos
* Realce de sintaxe para várias linguagens de programação
* Busca e substituição de texto com suporte a expressões regulares
* Seleção de texto com suporte a copiar e colar
* Formatação automática de código (Python e JavaScript)
* Desfazer/Refazer ilimitado
* Interface com caixas desenhadas em ASCII e uso de símbolos Nerd Fonts
* Suporte a redimensionamento do terminal
* Modo de inserção e sobrescrita
* Navegação por linha e busca incremental

## Preview

![Screenshot](screenshot.png)

## Requisitos

* Python 3.6 ou superior
* Biblioteca `curses` (para interface TUI)
* Terminal compatível com `curses` (Linux, macOS, WSL)
* Bibliotecas opcionais para formatação de código:
  * `autopep8` (para Python)
  * `jsbeautifier` (para JavaScript)

> **Atenção:** Suporte oficial apenas para Linux, macOS e WSL. Usuários Windows podem tentar rodar instalando o pacote `windows-curses`, mas não há garantia de funcionamento ou suporte.

Instalação das dependências opcionais:

```bash
pip install autopep8 jsbeautifier
```

## Uso

Execute o script diretamente pelo terminal:

```bash
python3 hydroedit.py [arquivo]
```

### Atalhos de Teclado

* `Ctrl+H` - Mostrar ajuda
* `Ctrl+O` - Salvar arquivo
* `Ctrl+X` - Sair
* `Ctrl+K` - Cortar texto
* `Ctrl+U` - Colar texto
* `Ctrl+Z` - Desfazer
* `Ctrl+Y` - Refazer
* `Ctrl+F` - Formatar código
* `Ctrl+W` - Buscar texto
* `Ctrl+\` - Substituir texto
* `Ctrl+_` - Ir para linha
* `Ctrl+A` - Início da linha
* `Ctrl+E` - Fim da linha
* `Ctrl+B` - Início do arquivo
* `Ctrl+V` - Fim do arquivo
* `Insert` - Alternar modo de inserção/sobrescrita

## Estrutura do Código

* Uso da biblioteca `curses` para criar a interface interativa
* Sistema de comandos para desfazer/refazer
* Gerenciamento de estado do editor
* Realce de sintaxe com cache de regex
* Sistema de busca avançada
* Tratamento para evitar erros ao desenhar em terminais pequenos

## Considerações

HydroEdit é considerado estável. Sugestões e contribuições são bem-vindas via issues ou pull requests no repositório.

## Contato

Para dúvidas ou sugestões, abra uma issue ou entre em contato via email.

  <p class="center">
    <img src="https://capsule-render.vercel.app/api?type=waving&color=8BE9FD&height=120&section=footer" alt="HydroEdit Footer" />
  </p> 