#!/usr/bin/env python3
import curses
import os
import sys
import re
import signal
from collections import deque
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

# Desabilita Ctrl+C
signal.signal(signal.SIGINT, signal.SIG_IGN)

@dataclass
class EditorState:
    """Classe para gerenciar o estado do editor."""
    content: List[str]
    cursor_y: int
    cursor_x: int
    scroll_y: int
    cutbuf: str = ""
    selection_start: Optional[Tuple[int, int]] = None
    selection_end: Optional[Tuple[int, int]] = None
    insert_mode: bool = True
    is_modified: bool = False
    filepath: str = ""
    language: Optional[str] = None
    message: str = ""
    shift_pressed: bool = False

    def ensure_valid_cursor_position(self):
        """Garante que a posição do cursor é válida."""
        self.cursor_y = max(0, min(self.cursor_y, len(self.content) - 1))
        self.cursor_x = max(0, min(self.cursor_x, len(self.content[self.cursor_y])))

    def update_selection(self):
        """Atualiza a seleção com base na posição atual do cursor."""
        if self.selection_start is None:
            self.selection_start = (self.cursor_y, self.cursor_x)
        self.selection_end = (self.cursor_y, self.cursor_x)

    def clear_selection(self):
        """Limpa a seleção atual."""
        self.selection_start = None
        self.selection_end = None

@dataclass
class SearchState:
    """Classe para gerenciar o estado da busca."""
    pattern: str = ""
    case_sensitive: bool = True
    whole_word: bool = False
    regex: bool = False
    current_match: int = -1
    matches: List[Tuple[int, int]] = field(default_factory=list)
    search_active: bool = False
    search_in_selection: bool = False
    incremental: bool = True
    scroll_y: int = 0
    last_search: str = ""
    search_history: List[str] = field(default_factory=list)
    history_index: int = -1

    def reset(self):
        """Reseta o estado da busca."""
        self.pattern = ""
        self.current_match = -1
        self.matches = []
        self.search_active = False
        self.search_in_selection = False
        self.scroll_y = 0
        self.whole_word = False
        self.regex = False

    def next_match(self) -> Optional[Tuple[int, int]]:
        """Retorna a próxima ocorrência."""
        if not self.matches:
            return None
        self.current_match = (self.current_match + 1) % len(self.matches)
        return self.matches[self.current_match]

    def previous_match(self) -> Optional[Tuple[int, int]]:
        """Retorna a ocorrência anterior."""
        if not self.matches:
            return None
        self.current_match = (self.current_match - 1) % len(self.matches)
        return self.matches[self.current_match]

    def add_to_history(self, pattern: str):
        """Adiciona um padrão ao histórico de busca."""
        if pattern and pattern != self.last_search:
            self.search_history.append(pattern)
            self.last_search = pattern
            self.history_index = len(self.search_history) - 1

    def get_previous_search(self) -> Optional[str]:
        """Retorna o padrão de busca anterior do histórico."""
        if self.history_index > 0:
            self.history_index -= 1
            return self.search_history[self.history_index]
        return None

    def get_next_search(self) -> Optional[str]:
        """Retorna o próximo padrão de busca do histórico."""
        if self.history_index < len(self.search_history) - 1:
            self.history_index += 1
            return self.search_history[self.history_index]
        return None

class Command(ABC):
    """Classe base abstrata para comandos do editor."""
    
    @abstractmethod
    def execute(self, state: EditorState) -> None:
        """Executa o comando."""
        pass

    @abstractmethod
    def undo(self, state: EditorState) -> None:
        """Desfaz o comando."""
        pass

class MoveCommand(Command):
    """Comando para mover o cursor."""
    
    def __init__(self, direction: str, amount: int = 1):
        self.direction = direction
        self.amount = amount
        self.old_y = 0
        self.old_x = 0

    def execute(self, state: EditorState) -> None:
        self.old_y = state.cursor_y
        self.old_x = state.cursor_x
        
        if self.direction == "up":
            state.cursor_y = max(0, state.cursor_y - self.amount)
        elif self.direction == "down":
            state.cursor_y = min(len(state.content) - 1, state.cursor_y + self.amount)
        elif self.direction == "left":
            state.cursor_x = max(0, state.cursor_x - self.amount)
        elif self.direction == "right":
            state.cursor_x = min(len(state.content[state.cursor_y]), state.cursor_x + self.amount)
        
        state.cursor_x = min(state.cursor_x, len(state.content[state.cursor_y]))
        
        if state.shift_pressed:
            state.update_selection()
        else:
            state.clear_selection()

    def undo(self, state: EditorState) -> None:
        state.cursor_y = self.old_y
        state.cursor_x = self.old_x

class InsertCommand(Command):
    """Comando para inserir texto."""
    
    def __init__(self, char: str):
        self.char = char
        self.old_y = 0
        self.old_x = 0

    def execute(self, state: EditorState) -> None:
        self.old_y = state.cursor_y
        self.old_x = state.cursor_x
        
        if state.insert_mode:
            state.content[state.cursor_y] = (
                state.content[state.cursor_y][:state.cursor_x] +
                self.char +
                state.content[state.cursor_y][state.cursor_x:]
            )
        else:
            if state.cursor_x < len(state.content[state.cursor_y]):
                state.content[state.cursor_y] = (
                    state.content[state.cursor_y][:state.cursor_x] +
                    self.char +
                    state.content[state.cursor_y][state.cursor_x+1:]
                )
            else:
                state.content[state.cursor_y] = (
                    state.content[state.cursor_y][:state.cursor_x] +
                    self.char
                )
        
        state.cursor_x += 1
        state.is_modified = True
        state.clear_selection()

    def undo(self, state: EditorState) -> None:
        state.content[state.cursor_y] = (
            state.content[state.cursor_y][:state.cursor_x-1] +
            state.content[state.cursor_y][state.cursor_x:]
        )
        state.cursor_y = self.old_y
        state.cursor_x = self.old_x

class BackspaceCommand(Command):
    """Comando para apagar o caractere anterior."""
    
    def __init__(self):
        self.old_y = 0
        self.old_x = 0
        self.deleted_char = ""

    def execute(self, state: EditorState) -> None:
        self.old_y = state.cursor_y
        self.old_x = state.cursor_x
        
        if state.cursor_x > 0:
            self.deleted_char = state.content[state.cursor_y][state.cursor_x-1]
            state.content[state.cursor_y] = (
                state.content[state.cursor_y][:state.cursor_x-1] +
                state.content[state.cursor_y][state.cursor_x:]
            )
            state.cursor_x -= 1
        elif state.cursor_y > 0:
            self.deleted_char = "\n"
            state.cursor_x = len(state.content[state.cursor_y-1])
            state.content[state.cursor_y-1] += state.content[state.cursor_y]
            del state.content[state.cursor_y]
            state.cursor_y -= 1
        
        state.is_modified = True
        state.clear_selection()

    def undo(self, state: EditorState) -> None:
        if self.deleted_char == "\n":
            state.content[state.cursor_y] = (
                state.content[state.cursor_y][:state.cursor_x] +
                "\n" +
                state.content[state.cursor_y][state.cursor_x:]
            )
            state.cursor_y += 1
            state.cursor_x = 0
        else:
            state.content[state.cursor_y] = (
                state.content[state.cursor_y][:state.cursor_x] +
                self.deleted_char +
                state.content[state.cursor_y][state.cursor_x:]
            )
            state.cursor_x += 1

class DeleteCommand(Command):
    """Comando para apagar o caractere atual."""
    
    def __init__(self):
        self.old_y = 0
        self.old_x = 0
        self.deleted_char = ""

    def execute(self, state: EditorState) -> None:
        self.old_y = state.cursor_y
        self.old_x = state.cursor_x
        
        if state.cursor_x < len(state.content[state.cursor_y]):
            self.deleted_char = state.content[state.cursor_y][state.cursor_x]
            state.content[state.cursor_y] = (
                state.content[state.cursor_y][:state.cursor_x] +
                state.content[state.cursor_y][state.cursor_x+1:]
            )
        elif state.cursor_y < len(state.content) - 1:
            self.deleted_char = "\n"
            state.content[state.cursor_y] += state.content[state.cursor_y+1]
            del state.content[state.cursor_y+1]
        
        state.is_modified = True
        state.clear_selection()

    def undo(self, state: EditorState) -> None:
        if self.deleted_char == "\n":
            state.content[state.cursor_y] = (
                state.content[state.cursor_y][:state.cursor_x] +
                "\n" +
                state.content[state.cursor_y][state.cursor_x:]
            )
            state.cursor_y += 1
            state.cursor_x = 0
        else:
            state.content[state.cursor_y] = (
                state.content[state.cursor_y][:state.cursor_x] +
                self.deleted_char +
                state.content[state.cursor_y][state.cursor_x:]
            )

class EnterCommand(Command):
    """Comando para inserir uma nova linha."""
    
    def __init__(self):
        self.old_y = 0
        self.old_x = 0

    def execute(self, state: EditorState) -> None:
        self.old_y = state.cursor_y
        self.old_x = state.cursor_x
        
        # Preserva a indentação da linha atual
        indent = len(state.content[state.cursor_y]) - len(state.content[state.cursor_y].lstrip())
        indent_str = ' ' * indent
        
        # Insere a nova linha
        new_line = indent_str + state.content[state.cursor_y][state.cursor_x:]
        state.content[state.cursor_y] = state.content[state.cursor_y][:state.cursor_x]
        state.content.insert(state.cursor_y + 1, new_line)
        
        state.cursor_y += 1
        state.cursor_x = indent
        state.is_modified = True
        state.clear_selection()

    def undo(self, state: EditorState) -> None:
        state.content[state.cursor_y-1] += state.content[state.cursor_y]
        del state.content[state.cursor_y]
        state.cursor_y = self.old_y
        state.cursor_x = self.old_x

class ReplaceCommand(Command):
    """Comando para substituir texto."""
    
    def __init__(self, pattern: str, replacement: str, case_sensitive: bool = True):
        self.pattern = pattern
        self.replacement = replacement
        self.case_sensitive = case_sensitive
        self.old_content = []

    def execute(self, state: EditorState) -> None:
        self.old_content = state.content.copy()
        state.content = replace_text(state.content, self.pattern, self.replacement, self.case_sensitive)
        state.is_modified = True

    def undo(self, state: EditorState) -> None:
        state.content = self.old_content

class FormatCommand(Command):
    """Comando para formatar o código."""
    
    def __init__(self):
        self.old_content = []

    def execute(self, state: EditorState) -> None:
        self.old_content = state.content.copy()
        state.content = format_code(state.content, state.language)
        state.is_modified = True

    def undo(self, state: EditorState) -> None:
        state.content = self.old_content

class CommandHandler:
    """Classe para gerenciar comandos do editor."""
    
    def __init__(self):
        self.undo_stack = deque(maxlen=MAX_UNDO)
        self.redo_stack = deque(maxlen=MAX_UNDO)

    def execute_command(self, command: Command, state: EditorState) -> None:
        """Executa um comando e o adiciona à pilha de desfazer."""
        command.execute(state)
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self, state: EditorState) -> None:
        """Desfaz o último comando."""
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo(state)
            self.redo_stack.append(command)

    def redo(self, state: EditorState) -> None:
        """Refaz o último comando desfeito."""
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.execute(state)
            self.undo_stack.append(command)

TL, TR, BL, BR = '╭', '╮', '╰', '╯'
H, V = '─', '│'

MIN_WIDTH, MIN_HEIGHT = 80, 24
MAX_UNDO = 100

# Símbolos Nerd Font
ICON_SAVE = "󰆓 "  # Salvar
ICON_ERROR = "󰅚 "  # Erro
ICON_HELP = "󰋗 "  # Ajuda
ICON_EXIT = "󰅚 "  # Sair
ICON_SEARCH = "󰍉 "  # Buscar
ICON_CUT = "󰆐 "  # Cortar
ICON_PASTE = "󰆏 "  # Colar
ICON_UNDO = "󰑊 "  # Desfazer
ICON_REDO = "󰑋 "  # Refazer

# Cores para realce de sintaxe
COLOR_KEYWORD = 6
COLOR_STRING = 7
COLOR_COMMENT = 8
COLOR_FUNCTION = 9
COLOR_NUMBER = 10
COLOR_OPERATOR = 11
COLOR_HTML_TAG = 12
COLOR_CSS_PROP = 13
COLOR_CSS_VALUE = 14
COLOR_PREPROCESSOR = 15
COLOR_VARIABLE = 16
COLOR_SYMBOL = 17
COLOR_XML_TAG = 18
COLOR_XML_ATTRIBUTE = 19
COLOR_XML_ENTITY = 20
COLOR_XML_CDATA = 21
COLOR_XML_DOCTYPE = 22
COLOR_XML_PROCESSING = 23
COLOR_TOML_TABLE = 24
COLOR_TOML_KEY = 25
COLOR_TOML_BOOLEAN = 26
COLOR_TOML_DATE = 27
COLOR_TOML_ARRAY = 28
COLOR_YAML_KEY = 29
COLOR_YAML_ANCHOR = 30
COLOR_YAML_ALIAS = 31
COLOR_YAML_TAG = 32
COLOR_YAML_DIRECTIVE = 33
COLOR_YAML_LIST = 34
COLOR_YAML_DOCUMENT = 35
COLOR_JSON_KEY = 36
COLOR_JSON_BOOLEAN = 37
COLOR_JSON_OPERATOR = 38

# Cores para Markdown
COLOR_MD_HEADER = 39
COLOR_MD_BOLD = 40
COLOR_MD_ITALIC = 41
COLOR_MD_CODE = 42
COLOR_MD_LINK = 43
COLOR_MD_IMAGE = 44
COLOR_MD_LIST = 45
COLOR_MD_QUOTE = 46
COLOR_MD_RULE = 47
COLOR_MD_TABLE = 48
COLOR_MD_STRIKE = 49
COLOR_MD_HIGHLIGHT = 50
COLOR_MD_FOOTNOTE = 51
COLOR_MD_TASK = 52

# Padrões de sintaxe por linguagem
SYNTAX_PATTERNS = {
    'python': {
        'keywords': r'\b(def|class|if|else|elif|while|for|in|try|except|finally|with|as|import|from|return|break|continue|pass|raise|yield|async|await|True|False|None)\b',
        'strings': r'(\'.*?\'|\".*?\")',
        'comments': r'(#.*?)$',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?\b',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'json': {
        'strings': r'(\".*?\")',
        'numbers': r'\b\d+(\.\d+)?(e[+-]?\d+)?\b',
        'booleans': r'\b(true|false|null)\b',
        'keys': r'(\"[a-zA-Z0-9_-]+\")(?=\s*:)',
        'operators': r'[{}\[\]\:,]',
        'whitespace': r'\s+'
    },
    'toml': {
        'comments': r'(#.*?)$',
        'strings': r'(\'.*?\'|\".*?\"|""".*?""")',
        'numbers': r'\b\d+(\.\d+)?(e[+-]?\d+)?\b',
        'booleans': r'\b(true|false)\b',
        'dates': r'\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?',
        'tables': r'^\[.*?\]',
        'arrays': r'\[.*?\]',
        'keys': r'^[a-zA-Z0-9_-]+(?=\s*=)',
        'operators': r'[=]'
    },
    'javascript': {
        'keywords': r'\b(function|var|let|const|if|else|while|for|in|of|try|catch|finally|return|break|continue|switch|case|default|class|extends|new|this|super|import|export|async|await|true|false|null|undefined)\b',
        'strings': r'(\'.*?\'|\".*?\"|`.*?`)',
        'comments': r'(//.*?$|/\*.*?\*/)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?\b',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'html': {
        'tags': r'(<[^>]+>)',
        'strings': r'(\'.*?\'|\".*?\")',
        'comments': r'(<!--.*?-->)',
        'attributes': r'(\w+)=',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'css': {
        'properties': r'([a-zA-Z-]+):',
        'values': r':\s*([^;]+)',
        'comments': r'(/\*.*?\*/)',
        'selectors': r'([.#]?[a-zA-Z][\w-]*)',
        'numbers': r'\b\d+(\.\d+)?(px|em|rem|%|vh|vw)?\b'
    },
    'java': {
        'keywords': r'\b(public|private|protected|class|interface|extends|implements|static|final|void|int|long|float|double|boolean|char|String|if|else|while|for|do|switch|case|break|continue|return|try|catch|finally|throw|throws|new|this|super|import|package)\b',
        'strings': r'(\'.*?\'|\".*?\")',
        'comments': r'(//.*?$|/\*.*?\*/)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?\b',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'bash': {
        'keywords': r'\b(if|then|else|elif|fi|for|while|until|do|done|case|esac|function|return|exit|break|continue|local|readonly|declare|export|source|\.|echo|printf|test|[|]|&&|\|\|)\b',
        'strings': r'(\'.*?\'|\".*?\")',
        'comments': r'(#.*?)$',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(\)',
        'numbers': r'\b\d+\b',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'rust': {
        'keywords': r'\b(fn|let|mut|const|if|else|while|for|in|loop|match|return|break|continue|struct|enum|impl|trait|use|mod|pub|unsafe|async|await|true|false|None|Some|Ok|Err)\b',
        'strings': r'(\'.*?\'|\".*?\"|r#".*?"#)',
        'comments': r'(//.*?$|/\*.*?\*/)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?\b',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'go': {
        'keywords': r'\b(func|var|const|if|else|for|range|switch|case|default|return|break|continue|defer|go|chan|select|struct|interface|type|import|package)\b',
        'strings': r'(\'.*?\'|\".*?\")',
        'comments': r'(//.*?$|/\*.*?\*/)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?\b',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'c': {
        'keywords': r'\b(int|char|float|double|void|struct|union|enum|typedef|static|extern|const|volatile|register|auto|signed|unsigned|short|long|if|else|switch|case|default|for|while|do|break|continue|return|goto|sizeof)\b',
        'strings': r'(\'.*?\'|\".*?\")',
        'comments': r'(//.*?$|/\*.*?\*/)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?(u|U|l|L|f|F)?\b',
        'operators': r'[+\-*/=<>!&|^~]+',
        'preprocessor': r'#\s*(include|define|undef|ifdef|ifndef|endif|if|else|elif|line|error|pragma)'
    },
    'cpp': {
        'keywords': r'\b(class|namespace|template|typename|public|private|protected|virtual|override|final|explicit|friend|inline|mutable|operator|using|typedef|constexpr|decltype|auto|nullptr|true|false|and|or|not|bitand|bitor|compl|and_eq|or_eq|xor_eq|not_eq)\b',
        'strings': r'(\'.*?\'|\".*?\"|R"\(.*?\)")',
        'comments': r'(//.*?$|/\*.*?\*/)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?(u|U|l|L|f|F)?\b',
        'operators': r'[+\-*/=<>!&|^~]+',
        'preprocessor': r'#\s*(include|define|undef|ifdef|ifndef|endif|if|else|elif|line|error|pragma)'
    },
    'php': {
        'keywords': r'\b(abstract|and|array|as|break|callable|case|catch|class|clone|const|continue|declare|default|die|do|echo|else|elseif|empty|enddeclare|endfor|endforeach|endif|endswitch|endwhile|eval|exit|extends|final|finally|for|foreach|function|global|goto|if|implements|include|include_once|instanceof|insteadof|interface|isset|list|namespace|new|or|print|private|protected|public|require|require_once|return|static|switch|throw|trait|try|unset|use|var|while|xor|yield)\b',
        'strings': r'(\'.*?\'|\".*?\"|`.*?`)',
        'comments': r'(//.*?$|/\*.*?\*/|#.*?$)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?\b',
        'operators': r'[+\-*/=<>!&|^~]+',
        'variables': r'\$[a-zA-Z_\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*'
    },
    'ruby': {
        'keywords': r'\b(alias|and|begin|break|case|class|def|defined\?|do|else|elsif|end|ensure|false|for|if|in|module|next|nil|not|or|redo|rescue|retry|return|self|super|then|true|undef|unless|until|when|while|yield)\b',
        'strings': r'(\'.*?\'|\".*?\"|%[qQ]?[\[\(].*?[\]\)]|<<-?[A-Za-z_][A-Za-z0-9_]*\n.*?\n[A-Za-z_][A-Za-z0-9_]*)',
        'comments': r'(#.*?$|=begin.*?=end)',
        'functions': r'\b([a-zA-Z_]\w*)\s*(?=\()',
        'numbers': r'\b\d+(\.\d+)?\b',
        'operators': r'[+\-*/=<>!&|^~]+',
        'symbols': r':[a-zA-Z_]\w*'
    },
    'swift': {
        'keywords': r'\b(associatedtype|class|deinit|enum|extension|fileprivate|func|import|init|inout|internal|let|open|operator|private|protocol|public|rethrows|static|struct|subscript|typealias|var|break|case|continue|default|defer|do|else|fallthrough|for|guard|if|in|repeat|return|switch|where|while|as|Any|catch|false|is|nil|super|self|Self|throw|throws|true|try|#available|#colorLiteral|#column|#else|#elseif|#endif|#file|#fileLiteral|#function|#if|#imageLiteral|#line|#selector|#sourceLocation)\b',
        'strings': r'(\'.*?\'|\".*?\"|"""[\s\S]*?""")',
        'comments': r'(//.*?$|/\*.*?\*/)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?\b',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'kotlin': {
        'keywords': r'\b(as|break|class|continue|do|else|false|for|fun|if|in|interface|is|null|object|package|return|super|this|throw|true|try|typealias|typeof|val|var|when|while|by|catch|constructor|delegate|dynamic|field|file|finally|get|import|init|param|property|receiver|set|setparam|where|actual|abstract|annotation|companion|const|crossinline|data|enum|expect|external|final|infix|inline|inner|internal|lateinit|noinline|open|operator|out|override|private|protected|public|reified|sealed|suspend|tailrec|vararg)\b',
        'strings': r'(\'.*?\'|\".*?\"|""".*?""")',
        'comments': r'(//.*?$|/\*.*?\*/)',
        'functions': r'\b([a-zA-Z_]\w*)\s*\(',
        'numbers': r'\b\d+(\.\d+)?(L|F|D)?\b',
        'operators': r'[+\-*/=<>!&|^~]+'
    },
    'xml': {
        'tags': r'(<[^>]+>)',
        'strings': r'(\'.*?\'|\".*?\")',
        'comments': r'(<!--.*?-->)',
        'attributes': r'(\w+)=',
        'operators': r'[+\-*/=<>!&|^~]+',
        'entities': r'&[a-zA-Z]+;',
        'cdata': r'<!\[CDATA\[.*?\]\]>',
        'doctype': r'<!DOCTYPE.*?>',
        'processing': r'<\?.*?\?>'
    },
    'yaml': {
        'comments': r'(#.*?)$',
        'strings': r'(\'.*?\'|\".*?\"|>.*?$|\|.*?$)',
        'numbers': r'\b\d+(\.\d+)?(e[+-]?\d+)?\b',
        'booleans': r'\b(true|false|yes|no|on|off)\b',
        'dates': r'\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?',
        'keys': r'^[a-zA-Z0-9_-]+(?=\s*:)',
        'anchors': r'&[a-zA-Z0-9_-]+',
        'aliases': r'\*[a-zA-Z0-9_-]+',
        'tags': r'![a-zA-Z0-9_-]+',
        'directives': r'^%[A-Z]+',
        'operators': r'[=:]',
        'lists': r'^\s*-\s',
        'documents': r'^---$|^\.\.\.$'
    },
    'markdown': {
        'headers': r'^(#{1,6})\s+(.+)$',
        'bold': r'\*\*(.+?)\*\*',
        'italic': r'\*(.+?)\*',
        'code_blocks': r'```[\s\S]*?```',
        'inline_code': r'`[^`]+`',
        'links': r'\[([^\]]+)\]\(([^)]+)\)',
        'images': r'!\[([^\]]*)\]\(([^)]+)\)',
        'lists': r'^(\s*)[*+-]\s+(.+)$',
        'numbered_lists': r'^(\s*)\d+\.\s+(.+)$',
        'blockquotes': r'^>\s+(.+)$',
        'horizontal_rules': r'^[-*_]{3,}$',
        'tables': r'^\|.+\|$',
        'strikethrough': r'~~(.+?)~~',
        'highlight': r'==(.+?)==',
        'footnotes': r'\[\^([^\]]+)\]',
        'task_lists': r'^(\s*)[*+-]\s+\[([ xX])\]\s+(.+)$'
    }
}

# Cache para padrões de regex compilados
SYNTAX_PATTERNS_COMPILED = {}

def compile_patterns():
    """Compila os padrões de regex uma única vez."""
    for lang, patterns in SYNTAX_PATTERNS.items():
        SYNTAX_PATTERNS_COMPILED[lang] = {
            pattern_type: re.compile(pattern)
            for pattern_type, pattern in patterns.items()
        }

# Compila os padrões na inicialização
compile_patterns()

def highlight_syntax(line, language):
    """Versão otimizada do realce de sintaxe com cache de regex."""
    if not language or language not in SYNTAX_PATTERNS_COMPILED:
        return [(0, line)]
    
    patterns = SYNTAX_PATTERNS_COMPILED[language]
    highlights = []
    last_end = 0
    
    # Processa cada tipo de padrão
    for pattern_type, pattern in patterns.items():
        for match in pattern.finditer(line):
            start, end = match.span()
            if start >= last_end:
                if start > last_end:
                    highlights.append((0, line[last_end:start]))
                color = {
                    'keywords': COLOR_KEYWORD,
                    'strings': COLOR_STRING,
                    'comments': COLOR_COMMENT,
                    'functions': COLOR_FUNCTION,
                    'numbers': COLOR_NUMBER,
                    'operators': COLOR_OPERATOR if language != 'json' else COLOR_JSON_OPERATOR,
                    'tags': COLOR_HTML_TAG if language != 'xml' else COLOR_XML_TAG,
                    'properties': COLOR_CSS_PROP,
                    'values': COLOR_CSS_VALUE,
                    'preprocessor': COLOR_PREPROCESSOR,
                    'variables': COLOR_VARIABLE,
                    'symbols': COLOR_SYMBOL,
                    'attributes': COLOR_XML_ATTRIBUTE,
                    'entities': COLOR_XML_ENTITY,
                    'cdata': COLOR_XML_CDATA,
                    'doctype': COLOR_XML_DOCTYPE,
                    'processing': COLOR_XML_PROCESSING,
                    'tables': COLOR_TOML_TABLE,
                    'keys': COLOR_TOML_KEY if language == 'toml' else (COLOR_YAML_KEY if language == 'yaml' else COLOR_JSON_KEY),
                    'booleans': COLOR_TOML_BOOLEAN if language != 'json' else COLOR_JSON_BOOLEAN,
                    'dates': COLOR_TOML_DATE,
                    'arrays': COLOR_TOML_ARRAY,
                    'anchors': COLOR_YAML_ANCHOR,
                    'aliases': COLOR_YAML_ALIAS,
                    'tags': COLOR_YAML_TAG if language == 'yaml' else COLOR_HTML_TAG,
                    'directives': COLOR_YAML_DIRECTIVE,
                    'lists': COLOR_YAML_LIST,
                    'documents': COLOR_YAML_DOCUMENT,
                    'headers': COLOR_MD_HEADER,
                    'bold': COLOR_MD_BOLD,
                    'italic': COLOR_MD_ITALIC,
                    'code_blocks': COLOR_MD_CODE,
                    'inline_code': COLOR_MD_CODE,
                    'links': COLOR_MD_LINK,
                    'images': COLOR_MD_IMAGE,
                    'lists': COLOR_MD_LIST,
                    'numbered_lists': COLOR_MD_LIST,
                    'blockquotes': COLOR_MD_QUOTE,
                    'horizontal_rules': COLOR_MD_RULE,
                    'tables': COLOR_MD_TABLE,
                    'strikethrough': COLOR_MD_STRIKE,
                    'highlight': COLOR_MD_HIGHLIGHT,
                    'footnotes': COLOR_MD_FOOTNOTE,
                    'task_lists': COLOR_MD_TASK
                }.get(pattern_type, 0)
                highlights.append((color, line[start:end]))
                last_end = end
    
    if last_end < len(line):
        highlights.append((0, line[last_end:]))
    
    return highlights

def draw_box(stdscr, y, x, h, w, title=""):
    try:
        stdscr.addstr(y, x, TL + H * (w-2) + TR)
        for i in range(1, h-1):
            stdscr.addstr(y+i, x, V + " " * (w-2) + V)
        stdscr.addstr(y+h-1, x, BL + H * (w-2) + BR)
        if title:
            stdscr.addstr(y, x + 2, f"[ {title} ]", curses.color_pair(3) | curses.A_BOLD)
    except curses.error:
        pass

def save_file(filepath, content):
    try:
        with open(filepath, "w") as f:
            # Preserva a última linha vazia se ela existir
            if content and content[-1] == '':
                f.write('\n'.join(content) + '\n')
            else:
                f.write('\n'.join(content))
        return True
    except:
        return False

def load_file(filepath):
    try:
        with open(filepath, "r") as f:
            content = f.read()
            # Se o arquivo termina com uma nova linha, preserva ela
            has_trailing_newline = content.endswith('\n')
            lines = content.splitlines()
            if has_trailing_newline:
                lines.append('')
            return lines if lines else ['']
    except:
        return ['']

def prompt_input(stdscr, prompt, default=""):
    curses.echo()
    stdscr.addstr(prompt)
    if default:
        stdscr.addstr(default)
    stdscr.refresh()
    inp = stdscr.getstr().decode()
    curses.noecho()
    return inp or default

def show_help(stdscr):
    h, w = stdscr.getmaxyx()
    help_h = 28  # Aumentei a altura para acomodar todos os comandos
    help_w = 60  # Largura da caixa de ajuda
    
    # Calcula a posição para centralizar na caixa de texto principal
    box_h, box_w = h - 4, w - 4  # Dimensões da caixa principal
    help_y = (box_h - help_h) // 2 + 1  # +1 para considerar o offset da caixa principal
    help_x = (box_w - help_w) // 2 + 2  # +2 para considerar o offset da caixa principal
    
    # Desenha a caixa de ajuda
    draw_box(stdscr, help_y, help_x, help_h, help_w, "Ajuda")
    
    # Lista de comandos e suas descrições
    commands = [
        ("Navegação:", ""),
        ("^A", "Início da linha"),
        ("^E", "Fim da linha"),
        ("^B", "Início do arquivo"),
        ("^V", "Fim do arquivo"),
        ("PgUp", "Página anterior"),
        ("PgDn", "Próxima página"),
        ("", ""),
        ("Edição:", ""),
        ("^K", "Cortar"),
        ("^U", "Colar"),
        ("^Z", "Desfazer"),
        ("^Y", "Refazer"),
        ("^F", "Formatar código"),
        ("", ""),
        ("Busca:", ""),
        ("^W", "Buscar texto"),
        ("^\\", "Substituir texto"),
        ("^_", "Ir para linha"),
        ("", ""),
        ("Arquivo:", ""),
        ("^O", "Salvar"),
        ("^X", "Sair"),
        ("", ""),
        ("^H", "Fechar ajuda"),
        ("", ""),
        ("", ""),
        ("", "")
    ]
    
    # Desenha os comandos
    for i, (cmd, desc) in enumerate(commands):
        y = help_y + 1 + i
        if y < help_y + help_h - 1:  # Evita desenhar fora da caixa
            # Desenha o comando
            safe_addstr(stdscr, y, help_x + 2, cmd, curses.color_pair(3))
            # Desenha a descrição
            safe_addstr(stdscr, y, help_x + 15, desc, curses.color_pair(3))
    
    stdscr.refresh()
    stdscr.getch()

def get_file_path(stdscr, prompt="Nome do arquivo: "):
    h, w = stdscr.getmaxyx()
    y = h - 3
    x = 2
    stdscr.addstr(y, x, " " * (w - 4))
    stdscr.addstr(y, x, prompt)
    stdscr.refresh()
    filepath = prompt_input(stdscr, prompt)
    if not filepath:
        return None
    if not os.path.isabs(filepath):
        filepath = os.path.join(os.getcwd(), filepath)
    return filepath

def search_text(content, pattern, start_y=0, start_x=0, case_sensitive=True, whole_word=False, regex=False, search_in_selection=False, selection_start=None, selection_end=None):
    """Busca texto no conteúdo e retorna todas as ocorrências."""
    if not pattern:
        return []
    
    try:
        if regex:
            if not case_sensitive:
                pattern = re.compile(pattern, re.IGNORECASE)
            else:
                pattern = re.compile(pattern)
        elif not case_sensitive:
            pattern = pattern.lower()
            content = [line.lower() for line in content]
        
        matches = []
        
        # Define o intervalo de busca
        if search_in_selection and selection_start and selection_end:
            start_line = min(selection_start[0], selection_end[0])
            end_line = max(selection_start[0], selection_end[0])
        else:
            start_line = 0
            end_line = len(content)
        
        # Busca todas as ocorrências
        for y in range(start_line, end_line):
            line = content[y]
            
            if regex:
                for match in pattern.finditer(line):
                    start, end = match.span()
                    if whole_word:
                        if (start == 0 or not line[start-1].isalnum()) and \
                           (end == len(line) or not line[end].isalnum()):
                            matches.append((y, start))
                    else:
                        matches.append((y, start))
            else:
                x = 0
                while True:
                    x = line.find(pattern, x)
                    if x == -1:
                        break
                    
                    if whole_word:
                        if (x == 0 or not line[x-1].isalnum()) and \
                           (x + len(pattern) == len(line) or not line[x + len(pattern)].isalnum()):
                            matches.append((y, x))
                    else:
                        matches.append((y, x))
                    
                    x += 1
        
        return matches
    except re.error:
        return []

def replace_text(content, pattern, replacement, case_sensitive=True):
    if not case_sensitive:
        pattern = pattern.lower()
        content = [line.lower() for line in content]
    
    return [line.replace(pattern, replacement) for line in content]

def has_unsaved_changes(content, filepath):
    try:
        with open(filepath, "r") as f:
            original_content = f.read().splitlines() or [""]
        return content != original_content
    except:
        return True

def confirm_exit(stdscr, content, filepath):
    h, w = stdscr.getmaxyx()
    msg = "Há alterações não salvas. O que deseja fazer?"
    y = h//2
    x = (w - len(msg))//2
    
    draw_box(stdscr, y-1, x-2, 5, len(msg)+4, "Confirmar Saída")
    stdscr.addstr(y, x, msg, curses.color_pair(3))
    stdscr.addstr(y+1, x, "S - Salvar e sair", curses.color_pair(3))
    stdscr.addstr(y+2, x, "N - Sair sem salvar", curses.color_pair(3))
    stdscr.addstr(y+3, x, "ESC - Cancelar", curses.color_pair(3))
    stdscr.refresh()
    
    while True:
        key = stdscr.getch()
        if key in (ord('s'), ord('S')):  # S
            if save_file(filepath, content):
                return True
            return False
        elif key in (ord('n'), ord('N')):  # N
            return True
        elif key == 27:  # ESC
            return False

def get_language_from_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    lang_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.java': 'java',
        '.sh': 'bash',
        '.bash': 'bash',
        '.rs': 'rust',
        '.go': 'go',
        '.ts': 'javascript',
        '.jsx': 'javascript',
        '.tsx': 'javascript',
        '.json': 'javascript',
        '.xml': 'html',
        '.md': 'markdown',
        '.txt': 'text',
        '.c': 'c',
        '.h': 'c',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.hpp': 'cpp',
        '.hxx': 'cpp',
        '.php': 'php',
        '.phtml': 'php',
        '.rb': 'ruby',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.kts': 'kotlin',
        '.toml': 'toml',
        '.yml': 'yaml',
        '.yaml': 'yaml'
    }
    return lang_map.get(ext)

def safe_addstr(stdscr, y, x, text, attr=0):
    try:
        h, w = stdscr.getmaxyx()
        if y >= h or x >= w:
            return 0
        text = text[:w - x]
        stdscr.addstr(y, x, text, attr)
        return len(text)
    except curses.error:
        return 0

def format_code(content, language):
    if language == 'python':
        try:
            import autopep8
            return autopep8.fix_code('\n'.join(content)).splitlines()
        except ImportError:
            return content
    elif language == 'javascript':
        try:
            import jsbeautifier
            opts = jsbeautifier.default_options()
            return jsbeautifier.beautify('\n'.join(content), opts).splitlines()
        except ImportError:
            return content
    return content

def show_status(stdscr, filepath, cursor_y, cursor_x, insert_mode, is_modified, message):
    h, w = stdscr.getmaxyx()
    status = f" {os.path.basename(filepath)} | Linha: {cursor_y + 1}, Col: {cursor_x + 1} | {'INS' if insert_mode else 'OVR'} | {'*' if is_modified else ''}"
    if message:
        status = f"{message} | {status}"
    stdscr.addstr(h-2, 0, status.ljust(w-1), curses.color_pair(3))
    help_msg = "Pressione ^H para ajuda"
    stdscr.addstr(h-2, w - len(help_msg) - 2, help_msg, curses.color_pair(4))

def show_message(stdscr, message, timeout=2):
    h, w = stdscr.getmaxyx()
    msg_w = len(message) + 4
    msg_x = (w - msg_w) // 2
    msg_y = h - 4
    
    draw_box(stdscr, msg_y-1, msg_x-2, 3, msg_w, "Mensagem")
    stdscr.addstr(msg_y, msg_x, message, curses.color_pair(3))
    stdscr.refresh()
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if stdscr.getch() != -1:
            break

# Cache para linhas quebradas
WRAP_CACHE = {}
WRAP_CACHE_SIZE = 1000  # Limite do tamanho do cache

def wrap_line(line, width):
    """Versão otimizada da quebra de linha com cache."""
    # Verifica se a linha está no cache
    cache_key = (line, width)
    if cache_key in WRAP_CACHE:
        return WRAP_CACHE[cache_key]
    
    if len(line) <= width:
        result = [line]
    else:
        # Preserva a indentação original
        indent = len(line) - len(line.lstrip())
        indent_str = ' ' * indent
        
        # Se a linha contém apenas espaços, retorna ela como está
        if not line.strip():
            result = [line]
        else:
            # Remove a indentação para processar o texto
            text = line[indent:]
            
            # Caracteres que podem ser usados para quebrar palavras
            break_chars = set(' -_.,;:!?/\\()[]{}<>|')
            
            # Função para quebrar uma palavra longa
            def break_long_word(word, max_width):
                if len(word) <= max_width:
                    return [word]
                
                parts = []
                current = ''
                for char in word:
                    if len(current) + 1 > max_width:
                        parts.append(current)
                        current = char
                    else:
                        current += char
                if current:
                    parts.append(current)
                return parts
            
            # Processa o texto
            words = text.split()
            if not words:
                result = [line]
            else:
                wrapped = []
                current_line = []
                current_length = 0
                max_content_width = width - indent
                
                for word in words:
                    # Se a palavra é maior que a largura disponível
                    if len(word) > max_content_width:
                        # Se já temos conteúdo na linha atual, adiciona ele
                        if current_line:
                            wrapped.append(indent_str + ' '.join(current_line))
                            current_line = []
                            current_length = 0
                        
                        # Quebra a palavra longa
                        word_parts = break_long_word(word, max_content_width)
                        wrapped.extend(indent_str + part for part in word_parts)
                        continue
                    
                    # Se adicionar a palavra ultrapassa a largura
                    if current_length + len(word) + (1 if current_line else 0) > max_content_width:
                        wrapped.append(indent_str + ' '.join(current_line))
                        current_line = [word]
                        current_length = len(word)
                    else:
                        current_line.append(word)
                        current_length += len(word) + (1 if current_line else 0)
                
                if current_line:
                    wrapped.append(indent_str + ' '.join(current_line))
                
                result = wrapped
    
    # Atualiza o cache
    if len(WRAP_CACHE) >= WRAP_CACHE_SIZE:
        # Remove o item mais antigo se o cache estiver cheio
        WRAP_CACHE.pop(next(iter(WRAP_CACHE)))
    WRAP_CACHE[cache_key] = result
    
    return result

def find_word_boundary(line, pos, forward=True):
    """Encontra o limite da próxima palavra na linha."""
    if forward:
        # Encontra o próximo caractere não-whitespace
        while pos < len(line) and line[pos].isspace():
            pos += 1
        # Encontra o próximo caractere whitespace
        while pos < len(line) and not line[pos].isspace():
            pos += 1
    else:
        # Encontra o próximo caractere não-whitespace para trás
        while pos > 0 and line[pos-1].isspace():
            pos -= 1
        # Encontra o próximo caractere whitespace para trás
        while pos > 0 and not line[pos-1].isspace():
            pos -= 1
    return pos

def update_selection(selection_start, selection_end, cursor_y, cursor_x):
    """Atualiza a seleção com base na posição atual do cursor."""
    if selection_start is None:
        return (cursor_y, cursor_x), (cursor_y, cursor_x)
    return selection_start, (cursor_y, cursor_x)

def get_display_line_index(content, cursor_y, text_width):
    """Converte o índice da linha do conteúdo para o índice da linha de exibição."""
    display_index = 0
    for i in range(cursor_y):
        wrapped = wrap_line(content[i], text_width)
        display_index += len(wrapped)
    return display_index

def get_content_line_index(display_lines, display_index):
    """Converte o índice da linha de exibição para o índice da linha do conteúdo."""
    if display_index >= len(display_lines):
        return len(display_lines) - 1
        
    # Cria um mapeamento entre linhas de exibição e linhas de conteúdo
    content_line_map = []
    current_content_line = 0
    
    for line in display_lines:
        content_line_map.append(current_content_line)
        # Se esta não é uma linha quebrada (não tem indentação extra)
        if not line.startswith(' ' * (len(line) - len(line.lstrip()))):
            current_content_line += 1
    
    return content_line_map[display_index]

def highlight_matches(stdscr, content, search_state, start_y, start_x, box_h, box_w):
    """Destaca todas as ocorrências do padrão de busca."""
    if not search_state.search_active or not search_state.pattern:
        return
    
    text_start_x = start_x + 2
    text_width = box_w - 4
    
    for match_y, match_x in search_state.matches:
        # Calcula a posição de exibição
        display_y = get_display_line_index(content, match_y, text_width) - search_state.scroll_y
        
        if 0 <= display_y < box_h - 2:
            # Desenha o destaque
            safe_addstr(stdscr, start_y + 1 + display_y, text_start_x + match_x,
                       search_state.pattern, curses.color_pair(5))

def show_search_bar(stdscr, search_state):
    """Mostra a barra de busca com opções avançadas."""
    h, w = stdscr.getmaxyx()
    y = h - 3
    x = 2
    
    # Limpa a linha
    stdscr.addstr(y, x, " " * (w - 4))
    
    # Desenha a barra de busca com opções
    search_text = f"Buscar: {search_state.pattern}"
    if search_state.matches:
        search_text += f" ({search_state.current_match + 1}/{len(search_state.matches)})"
    
    # Adiciona indicadores de opções
    options = []
    if search_state.case_sensitive:
        options.append("Aa")
    if search_state.whole_word:
        options.append("W")
    if search_state.regex:
        options.append("R")
    
    if options:
        search_text += f" [{','.join(options)}]"
    
    stdscr.addstr(y, x, search_text, curses.color_pair(3))
    
    # Mostra as opções de teclas
    help_text = "[Enter: Próximo] [Shift+Enter: Anterior] [ESC: Cancelar] [Tab: Opções]"
    stdscr.addstr(y, w - len(help_text) - 2, help_text, curses.color_pair(4))

def show_search_options(stdscr, search_state):
    """Mostra o menu de opções de busca."""
    h, w = stdscr.getmaxyx()
    options_h = 7
    options_w = 30
    y = h - options_h - 3
    x = 2
    
    draw_box(stdscr, y, x, options_h, options_w, "Opções de Busca")
    
    # Lista de opções
    options = [
        ("C - Case Sensitive", search_state.case_sensitive),
        ("W - Palavra Inteira", search_state.whole_word),
        ("R - Expressão Regular", search_state.regex),
        ("I - Busca Incremental", search_state.incremental),
        ("S - Buscar em Seleção", search_state.search_in_selection)
    ]
    
    for i, (text, active) in enumerate(options):
        status = "✓" if active else " "
        safe_addstr(stdscr, y + 1 + i, x + 2, f"{text}: [{status}]", curses.color_pair(3))
    
    stdscr.refresh()
    
    while True:
        key = stdscr.getch()
        if key == 27:  # ESC
            break
        elif key == ord('c'):
            search_state.case_sensitive = not search_state.case_sensitive
            break
        elif key == ord('w'):
            search_state.whole_word = not search_state.whole_word
            break
        elif key == ord('r'):
            search_state.regex = not search_state.regex
            break
        elif key == ord('i'):
            search_state.incremental = not search_state.incremental
            break
        elif key == ord('s'):
            search_state.search_in_selection = not search_state.search_in_selection
            break

def main(stdscr, initial_filepath=None):
    curses.curs_set(1)
    curses.start_color()
    curses.use_default_colors()
    stdscr.keypad(True)

    # Inicializa as cores
    curses.init_pair(COLOR_KEYWORD, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_STRING, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_COMMENT, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_FUNCTION, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_NUMBER, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_OPERATOR, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_HTML_TAG, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_CSS_PROP, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_CSS_VALUE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_PREPROCESSOR, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_VARIABLE, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_SYMBOL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_XML_TAG, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_XML_ATTRIBUTE, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_XML_ENTITY, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_XML_CDATA, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_XML_DOCTYPE, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_XML_PROCESSING, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_TOML_TABLE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_TOML_KEY, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_TOML_BOOLEAN, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_TOML_DATE, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_TOML_ARRAY, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_YAML_KEY, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_YAML_ANCHOR, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_YAML_ALIAS, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_YAML_TAG, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_YAML_DIRECTIVE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_YAML_LIST, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_YAML_DOCUMENT, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_JSON_KEY, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_JSON_BOOLEAN, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_JSON_OPERATOR, curses.COLOR_CYAN, -1)
    # Cores existentes
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
    
    # Cores para Markdown
    curses.init_pair(COLOR_MD_HEADER, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_MD_BOLD, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_MD_ITALIC, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_MD_CODE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_MD_LINK, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_MD_IMAGE, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_MD_LIST, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_MD_QUOTE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_MD_RULE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_MD_TABLE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_MD_STRIKE, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_MD_HIGHLIGHT, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_MD_FOOTNOTE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_MD_TASK, curses.COLOR_GREEN, -1)

    if initial_filepath:
        if not os.path.isabs(initial_filepath):
            initial_filepath = os.path.join(os.getcwd(), initial_filepath)
        filepath = initial_filepath
    else:
        filepath = os.path.join(os.getcwd(), "untitled.txt")
    
    content = load_file(filepath)
    if not content:  # Garante que sempre haja pelo menos uma linha vazia
        content = [""]
    language = get_language_from_file(filepath)

    # Inicializa o estado do editor
    state = EditorState(
        content=content,
        cursor_y=0,
        cursor_x=0,
        scroll_y=0,
        filepath=filepath,
        language=language
    )

    # Inicializa o estado da busca
    search_state = SearchState()

    # Inicializa o gerenciador de comandos
    command_handler = CommandHandler()

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        if h < MIN_HEIGHT or w < MIN_WIDTH:
            msg = f"Terminal pequeno demais {ICON_ERROR}"
            stdscr.addstr(h//2, max(0, (w - len(msg))//2), msg, curses.color_pair(2) | curses.A_BOLD)
            stdscr.refresh()
            stdscr.getch()
            continue

        box_h, box_w = h - 4, w - 4
        start_y, start_x = 1, 2
        draw_box(stdscr, start_y, start_x, box_h, box_w, f"HydroEdit - {os.path.basename(state.filepath)}")

        # Configuração do texto sem números de linha
        text_start_x = start_x + 2
        text_width = box_w - 4  # Largura disponível para o texto (com padding)

        # Desenha o conteúdo com suporte a seleção e realce de sintaxe
        display_lines = []
        for line in state.content:
            display_lines.extend(wrap_line(line, text_width))

        # Converte cursor_y para o índice de display_lines
        display_cursor_y = get_display_line_index(state.content, state.cursor_y, text_width)

        # Ajusta o scroll vertical para garantir que o cursor esteja visível
        while display_cursor_y - state.scroll_y >= box_h - 2:
            state.scroll_y += 1
        while display_cursor_y - state.scroll_y < 0:
            state.scroll_y -= 1

        # Garante que o scroll não ultrapasse o limite do conteúdo
        max_scroll = max(0, len(display_lines) - (box_h - 2))
        state.scroll_y = min(state.scroll_y, max_scroll)

        # Atualiza o scroll do SearchState
        if search_state.search_active:
            search_state.scroll_y = state.scroll_y

        # Desenha as linhas visíveis
        for i in range(box_h - 2):
            line_idx = state.scroll_y + i
            if line_idx < len(display_lines):
                line = display_lines[line_idx]
                x_pos = text_start_x
                
                # Obtém o índice da linha de conteúdo correspondente
                content_line = get_content_line_index(display_lines, line_idx)
                
                if state.selection_start and state.selection_end:
                    start_sel = state.selection_start if state.selection_start[0] < state.selection_end[0] else state.selection_end
                    end_sel = state.selection_end if state.selection_start[0] < state.selection_end[0] else state.selection_start
                    
                    if start_sel[0] <= content_line <= end_sel[0]:
                        # Calcula as posições relativas na linha
                        start_x_sel = start_sel[1] if content_line == start_sel[0] else 0
                        end_x_sel = end_sel[1] if content_line == end_sel[0] else len(line)
                        
                        # Desenha a parte antes da seleção com realce
                        for color, text in highlight_syntax(line[:start_x_sel], state.language):
                            if len(text) > 0:
                                safe_addstr(stdscr, start_y + 1 + i, x_pos, text, curses.color_pair(color))
                                x_pos += len(text)
                        
                        # Desenha a seleção
                        sel_text = line[start_x_sel:end_x_sel]
                        if sel_text:
                            safe_addstr(stdscr, start_y + 1 + i, x_pos, sel_text, curses.color_pair(5))
                            x_pos += len(sel_text)
                        
                        # Desenha a parte depois da seleção com realce
                        for color, text in highlight_syntax(line[end_x_sel:], state.language):
                            if len(text) > 0:
                                safe_addstr(stdscr, start_y + 1 + i, x_pos, text, curses.color_pair(color))
                                x_pos += len(text)
                    else:
                        # Desenha a linha inteira com realce
                        for color, text in highlight_syntax(line, state.language):
                            if len(text) > 0:
                                safe_addstr(stdscr, start_y + 1 + i, x_pos, text, curses.color_pair(color))
                                x_pos += len(text)
                else:
                    # Desenha a linha inteira com realce
                    for color, text in highlight_syntax(line, state.language):
                        if len(text) > 0:
                            safe_addstr(stdscr, start_y + 1 + i, x_pos, text, curses.color_pair(color))
                            x_pos += len(text)

        # Destaca as ocorrências da busca
        if search_state.search_active:
            highlight_matches(stdscr, state.content, search_state, start_y, start_x, box_h, box_w)

        show_status(stdscr, state.filepath, state.cursor_y, state.cursor_x, state.insert_mode, state.is_modified, state.message)

        # Mostra a barra de busca se estiver ativa
        if search_state.search_active:
            show_search_bar(stdscr, search_state)

        # Garante que a posição do cursor é válida antes de movê-lo
        state.ensure_valid_cursor_position()
        
        # Calcula a posição correta do cursor considerando o scroll
        cursor_display_y = display_cursor_y - state.scroll_y
        if 0 <= cursor_display_y < box_h - 2:
            stdscr.move(start_y + 1 + cursor_display_y, text_start_x + state.cursor_x)
        
        stdscr.refresh()

        key = stdscr.getch()
        state.message = ""
        
        # Verifica se Shift está pressionado
        if key == curses.KEY_SLEFT or key == curses.KEY_SRIGHT:
            state.shift_pressed = True
            if state.selection_start is None:
                state.selection_start = (state.cursor_y, state.cursor_x)
            state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
        else:
            state.shift_pressed = False
            if not (key == curses.KEY_UP or key == curses.KEY_DOWN or key == curses.KEY_LEFT or key == curses.KEY_RIGHT):
                state.selection_start = state.selection_end = None

        if search_state.search_active:
            if key == 27:  # ESC
                search_state.reset()
            elif key == 10:  # Enter
                if state.shift_pressed:
                    match = search_state.previous_match()
                else:
                    match = search_state.next_match()
                if match:
                    state.cursor_y, state.cursor_x = match
            elif key == curses.KEY_BACKSPACE or key == 127:
                if search_state.pattern:
                    search_state.pattern = search_state.pattern[:-1]
                    search_state.matches = search_text(state.content, search_state.pattern,
                                                     case_sensitive=search_state.case_sensitive,
                                                     search_in_selection=search_state.search_in_selection,
                                                     selection_start=state.selection_start,
                                                     selection_end=state.selection_end)
                    search_state.current_match = -1
            elif 32 <= key <= 126:
                search_state.pattern += chr(key)
                search_state.matches = search_text(state.content, search_state.pattern,
                                                 case_sensitive=search_state.case_sensitive,
                                                 search_in_selection=search_state.search_in_selection,
                                                 selection_start=state.selection_start,
                                                 selection_end=state.selection_end)
                search_state.current_match = -1
            continue

        if key == 8:  # Ctrl+H
            show_help(stdscr)
        elif key == 15:  # Ctrl+O
            if save_file(state.filepath, state.content):
                state.is_modified = False
                state.message = f"Salvo com sucesso! {ICON_SAVE}"
            else:
                state.message = f"Erro ao salvar {ICON_ERROR}"
        elif key == 24:  # Ctrl+X
            if state.is_modified:  # Só pergunta se houver modificações
                if not confirm_exit(stdscr, state.content, state.filepath):
                    continue
            break
        elif key == 11:  # Ctrl+K
            if state.selection_start and state.selection_end:
                start_sel = state.selection_start if state.selection_start[0] < state.selection_end[0] else state.selection_end
                end_sel = state.selection_end if state.selection_start[0] < state.selection_end[0] else state.selection_start
                state.cutbuf = "\n".join(state.content[start_sel[0]:end_sel[0]+1])
                del state.content[start_sel[0]:end_sel[0]+1]
                state.selection_start = state.selection_end = None
            elif 0 <= state.cursor_y < len(state.content):
                command_handler.execute_command(InsertCommand(state.content.pop(state.cursor_y)), state)
        elif key == 21:  # Ctrl+U
            if state.cutbuf:
                command_handler.execute_command(InsertCommand(state.cutbuf), state)
        elif key == 31:  # Ctrl+_
            line = prompt_input(stdscr, "Ir para linha: ")
            if line.isdigit():
                state.cursor_y = min(int(line)-1, len(state.content)-1)
                state.cursor_x = min(state.cursor_x, len(state.content[state.cursor_y]))
        elif key == 26:  # Ctrl+Z
            command_handler.undo(state)
        elif key == 25:  # Ctrl+Y
            command_handler.redo(state)
        elif key == 1:  # Ctrl+A
            state.cursor_x = 0
            if state.shift_pressed:
                state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
            else:
                state.selection_start = state.selection_end = None
        elif key == 5:  # Ctrl+E
            state.cursor_x = len(state.content[state.cursor_y])
            if state.shift_pressed:
                state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
            else:
                state.selection_start = state.selection_end = None
        elif key == 2:  # Ctrl+B (Início do arquivo)
            state.cursor_y = 0
            state.cursor_x = 0
            if state.shift_pressed:
                state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
            else:
                state.selection_start = state.selection_end = None
        elif key == 22:  # Ctrl+V (Fim do arquivo)
            state.cursor_y = len(state.content) - 1
            state.cursor_x = len(state.content[state.cursor_y])
            if state.shift_pressed:
                state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
            else:
                state.selection_start = state.selection_end = None
        elif key == curses.KEY_PPAGE:  # Page Up
            state.cursor_y = max(0, state.cursor_y - (box_h - 2))
            state.cursor_x = min(state.cursor_x, len(state.content[state.cursor_y]))
            if state.shift_pressed:
                state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
            else:
                state.selection_start = state.selection_end = None
        elif key == curses.KEY_NPAGE:  # Page Down
            state.cursor_y = min(len(state.content) - 1, state.cursor_y + (box_h - 2))
            state.cursor_x = min(state.cursor_x, len(state.content[state.cursor_y]))
            if state.shift_pressed:
                state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
            else:
                state.selection_start = state.selection_end = None
        elif key == 23:  # Ctrl+W
            search_state.search_active = True
            search_state.search_in_selection = bool(state.selection_start and state.selection_end)
            search_state.pattern = ""
            search_state.matches = []
            search_state.current_match = -1
        elif key == 28:  # Ctrl+\
            pattern = prompt_input(stdscr, "Substituir: ")
            if pattern:
                replacement = prompt_input(stdscr, "Substituir por: ")
                case_sensitive = prompt_input(stdscr, "Case sensitive? (S/n): ").lower() != 'n'
                command_handler.execute_command(ReplaceCommand(pattern, replacement, case_sensitive), state)
                state.message = f"Substituído '{pattern}' por '{replacement}'"
        elif key == 6:  # Ctrl+F
            command_handler.execute_command(FormatCommand(), state)
            state.message = "Código formatado"
        elif key == curses.KEY_IC:  # Tecla Insert
            state.insert_mode = not state.insert_mode
        elif key == curses.KEY_BACKSPACE or key == 127:
            command_handler.execute_command(BackspaceCommand(), state)
        elif key == curses.KEY_DC:  # Tecla Delete
            command_handler.execute_command(DeleteCommand(), state)
        elif key in (10, curses.KEY_ENTER):
            command_handler.execute_command(EnterCommand(), state)
        elif key == curses.KEY_UP:
            if state.cursor_y > 0:
                state.cursor_y -= 1
                state.cursor_x = min(state.cursor_x, len(state.content[state.cursor_y]))
                if state.shift_pressed:
                    state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
                else:
                    state.selection_start = state.selection_end = None
        elif key == curses.KEY_DOWN:
            if state.cursor_y < len(state.content) - 1:
                state.cursor_y += 1
                state.cursor_x = min(state.cursor_x, len(state.content[state.cursor_y]))
                if state.shift_pressed:
                    state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
                else:
                    state.selection_start = state.selection_end = None
        elif key == curses.KEY_LEFT:
            if state.cursor_x > 0:
                state.cursor_x -= 1
                if state.shift_pressed:
                    state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
                else:
                    state.selection_start = state.selection_end = None
        elif key == curses.KEY_RIGHT:
            if state.cursor_x < len(state.content[state.cursor_y]):
                state.cursor_x += 1
                if state.shift_pressed:
                    state.selection_start, state.selection_end = update_selection(state.selection_start, state.selection_end, state.cursor_y, state.cursor_x)
                else:
                    state.selection_start = state.selection_end = None
        elif key == 27:  # ESC
            state.selection_start = state.selection_end = None
            state.shift_pressed = False
        elif 32 <= key <= 126:
            command_handler.execute_command(InsertCommand(chr(key)), state)
        elif key == 9:  # Tab
            show_search_options(stdscr, search_state)
            # Atualiza a busca com as novas opções
            search_state.matches = search_text(state.content, search_state.pattern,
                                             case_sensitive=search_state.case_sensitive,
                                             whole_word=search_state.whole_word,
                                             regex=search_state.regex,
                                             search_in_selection=search_state.search_in_selection,
                                             selection_start=state.selection_start,
                                             selection_end=state.selection_end)
            search_state.current_match = -1
        elif key == curses.KEY_UP:  # Seta para cima no histórico
            prev_search = search_state.get_previous_search()
            if prev_search is not None:
                search_state.pattern = prev_search
                search_state.matches = search_text(state.content, search_state.pattern,
                                                 case_sensitive=search_state.case_sensitive,
                                                 whole_word=search_state.whole_word,
                                                 regex=search_state.regex,
                                                 search_in_selection=search_state.search_in_selection,
                                                 selection_start=state.selection_start,
                                                 selection_end=state.selection_end)
                search_state.current_match = -1
        elif key == curses.KEY_DOWN:  # Seta para baixo no histórico
            next_search = search_state.get_next_search()
            if next_search is not None:
                search_state.pattern = next_search
                search_state.matches = search_text(state.content, search_state.pattern,
                                                 case_sensitive=search_state.case_sensitive,
                                                 whole_word=search_state.whole_word,
                                                 regex=search_state.regex,
                                                 search_in_selection=search_state.search_in_selection,
                                                 selection_start=state.selection_start,
                                                 selection_end=state.selection_end)
                search_state.current_match = -1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        curses.wrapper(main, sys.argv[1])
    else:
        curses.wrapper(main)
