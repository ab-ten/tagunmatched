#!/usr/bin/env python3
import sys
import argparse
import unittest
from typing import Set

# PyYAML のインポート
import yaml

# 例外クラスの定義
class DSLSyntaxError(Exception):
  def __init__(self, line: int, col: int, message: str, stack: list):
    self.line = line
    self.col = col
    self.message = message
    self.stack = stack
    super().__init__(f"at line {line}, char {col}: {message} (Stack: {stack})")

  def __str__(self):
    return f"at line {self.line}, char {self.col}: {self.message} (Stack: {self.stack})"

# シンタックスチェッカー本体
class SyntaxChecker:
  def __init__(self, code: str, single_tags: Set[str], group_tags: Set[str], raise_exception: bool = False):
    self.code = code
    self.single_tags = single_tags
    self.group_tags = group_tags
    self.pos = 0
    self.line = 1
    self.col = 1
    self.stack = []  # グループタグのスタック
    self.raise_exception = raise_exception

  def current_char(self):
    if self.pos < len(self.code):
      return self.code[self.pos]
    return None

  def advance(self):
    ch = self.code[self.pos]
    self.pos += 1
    if ch == '\n':
      self.line += 1
      self.col = 1
    else:
      self.col += 1
    return ch

  def error(self, message: str) -> bool:
    err_msg = f"at line {self.line}, char {self.col}: {message}"
    if self.raise_exception:
      raise DSLSyntaxError(self.line, self.col, message, list(self.stack))
    else:
      print(err_msg)
      print(self.stack)
      return False

  def check(self) -> bool:
    while self.pos < len(self.code):
      ch = self.current_char()
      # タグ外や通常テキスト中のバッククオートによるエスケープ処理
      if ch == '`':
        self.advance()  # バッククオートを消費
        if self.current_char() is None:
          return self.error("単独のバッククオートが末尾に現れました")
        # 次の1文字は特殊機能を打ち消してただの文字として扱う
        self.advance()
        continue

      if ch == '[':
        # 未エスケープの '[' はタグ開始とみなす
        if not self.parse_tag():
          return False
        continue

      # タグ外の文字はそのまま消費
      self.advance()

    # 文字列終了時に未閉じタグが残っていればエラー
    if self.stack:
      return self.error("閉じられていないタグが残っています")
    return True

  def is_whitespace(self, ch: str) -> bool:
    return ch in [' ', '\t', '\n', '\r']

  def skip_whitespace(self):
    while self.current_char() is not None and self.is_whitespace(self.current_char()):
      self.advance()

  def parse_tag(self) -> bool:
    # 現在の文字は '[' と仮定
    self.advance()  # '[' を消費

    # 閉じタグかどうかの判定
    is_closing = False
    if self.current_char() == '/':
      is_closing = True
      self.advance()  # '/' を消費

    # タグ名のパース
    tag_name = ""
    ch = self.current_char()
    if ch is None:
      return self.error("タグ名がありません")
    if ch == '`':
      return self.error("タグ名にバッククオートが現れました")
    # タグ名の最初の文字は [#a-zA-Z0-9] である必要がございます
    if not (ch.isalnum() or ch == '#'):
      return self.error("タグ名の先頭文字が不正です")
    tag_name += ch
    self.advance()

    # タグ名の残りは [#a-zA-Z0-9_-]* とする
    while True:
      ch = self.current_char()
      if ch is None:
        return self.error("タグ名の途中で文字列が終了しました")
      if self.is_whitespace(ch) or ch == ']':
        break
      if ch == '`':
        return self.error("タグ名にバッククオートが現れました")
      if not (ch.isalnum() or ch in ['#', '_', '-']):
        return self.error("タグ名に不正な文字が含まれています")
      tag_name += ch
      self.advance()

    # タグ名と引数の間の空白（エスケープされていないもの）を消費
    self.skip_whitespace()

    # 引数のパース
    while self.current_char() is not None and self.current_char() != ']':
      # 連続する空白はひとつの区切りとして扱う
      if self.is_whitespace(self.current_char()):
        self.skip_whitespace()
        if self.current_char() == ']':
          break
        # 次の引数へ
      # 引数のパース開始
      if self.current_char() == '"':
        # ダブルクオートで囲まれた引数
        self.advance()  # 開始の " を消費
        while True:
          ch = self.current_char()
          if ch is None:
            return self.error("引用された引数が閉じられていません")
          if ch == '`':
            self.advance()
            if self.current_char() is None:
              return self.error("単独のバッククオートが末尾に現れました (引用内)")
            # バッククオートは次の文字を通常文字として扱う
            self.advance()
            continue
          if ch == '"':
            self.advance()  # 終了の " を消費
            break
          self.advance()
      else:
        # ダブルクオートで囲まれていない引数
        ch = self.current_char()
        if ch == '`':
          self.advance()
          if self.current_char() is None:
            return self.error("単独のバッククオートが末尾に現れました (非引用内)")
          self.advance()
          continue
        # エスケープされていない '[' はエラー
        if ch == '[':
          return self.error("非引用内の引数でエスケープされていない '[' が現れました")
        self.advance()

    # 引数パース終了後、タグの終了記号 ']' がなければエラー
    if self.current_char() != ']':
      return self.error("タグの終了記号 ']' が見つかりません")
    self.advance()  # ']' を消費

    # タグ種別に応じた処理
    if is_closing:
      if tag_name in self.single_tags:
        return self.error(f"閉じタグが不要なタグ [/{tag_name}] が現れました")
      if not self.stack:
        return self.error(f"閉じタグ [/{tag_name}] に対応する開始タグがありません")
      last_tag = self.stack.pop()
      if last_tag != tag_name:
        return self.error(f"閉じタグ [/{tag_name}] が直前の開始タグ [{last_tag}] と一致しません")
    else:
      if tag_name in self.single_tags:
        # 単一タグの場合はスタックに積まない
        pass
      elif tag_name in self.group_tags:
        self.stack.append(tag_name)
      else:
        return self.error(f"未知のタグ [{tag_name}] が現れました")
    return True

# エントリポイントの関数
def check_syntax(dsl_code: str, single_tags: Set[str], group_tags: Set[str], raise_exception: bool = False) -> bool:
  checker = SyntaxChecker(dsl_code, single_tags, group_tags, raise_exception)
  return checker.check()


##############################
# unittest を用いたテストケース群（以前のテストケース群）
##############################
class TestSyntaxChecker(unittest.TestCase):
  def setUp(self):
    self.single = {"br", "img"}
    self.group = {"b", "i", "u"}

  def test_no_tags(self):
    code = "これは単なるテキストです。"
    self.assertTrue(check_syntax(code, self.single, self.group))

  def test_simple_group_tag(self):
    code = "[b]太字のテキスト[/b]"
    self.assertTrue(check_syntax(code, self.single, self.group))

  def test_single_tag(self):
    code = "テキスト[br]次の行"
    self.assertTrue(check_syntax(code, self.single, self.group))

  def test_unclosed_group_tag(self):
    code = "[b]テスト"
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_unmatched_close_tag(self):
    code = "[b]テスト[/i]"
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_close_tag_for_single(self):
    code = "[/br]"
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_unknown_tag(self):
    code = "[unknown]テスト[/unknown]"
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_backquote_in_tag_name(self):
    code = "[b`]テスト[/b]"
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_unescaped_bracket_in_argument(self):
    code = "[b arg[illegal]]"
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_unclosed_quote(self):
    code = '[b "unterminated]'
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_single_backquote_at_end(self):
    code = "テキストの末尾にバッククオート`"
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_nested_three_levels_valid(self):
    code = "[b][i][u]Nested text[/u][/i][/b]"
    self.assertTrue(check_syntax(code, self.single, self.group))

  def test_nested_three_levels_invalid(self):
    code = "[b][i][u]Nested text[/i][/u][/b]"
    with self.assertRaises(DSLSyntaxError):
      check_syntax(code, self.single, self.group, raise_exception=True)

  def test_single_argument_with_escaped_quote(self):
    code = r'[b "arg with escaped quote: `""][/b]'
    self.assertTrue(check_syntax(code, self.single, self.group))

  def test_three_arguments_mixed(self):
    code = r'[b arg1 "arg2 with escaped quote: `""] "arg3 with escaped bracket: `["][/b]'
    self.assertTrue(check_syntax(code, self.single, self.group))

  def test_multiple_whitespace_arguments(self):
    code = r'[b  arg1   "arg2"  arg3][/b]'
    self.assertTrue(check_syntax(code, self.single, self.group))

  def test_multiple_whitespace_arguments2(self):
    code = r'[br sep=" "]'
    self.assertTrue(check_syntax(code, self.single, self.group, raise_exception=True))

  def test_text_with_escaped_brackets(self):
    code = r'This is a text with an escaped bracket: `[` and `].'
    self.assertTrue(check_syntax(code, self.single, self.group))


##############################
# メイン処理（argparse を用いた通常の実行およびテスト実行）
##############################
def main():
  parser = argparse.ArgumentParser(description="DSL Syntax Checker")
  parser.add_argument("--test", action="store_true", help="Run unit tests")
  parser.add_argument("-c", "--config", default="syntax-config.yaml",
            help="Path to configuration YAML file (default: syntax-config.yaml)")
  parser.add_argument("input_file", nargs="?", help="Path to the DSL file to check")
  args = parser.parse_args()

  if args.test:
    # --test が指定された場合は unittest を実行
    sys.argv = [sys.argv[0]]
    unittest.main()
  else:
    # positional argument の input_file が必須
    if args.input_file is None:
      parser.error("Input file is required when not running tests.")

    # 設定用 YAML ファイルを読み込み
    try:
      with open(args.config, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    except Exception as e:
      print(f"設定ファイルの読み込みに失敗しました: {e}")
      sys.exit(1)

    try:
      group_tags = set(config["syntax"]["group_tags"])
      single_tags = set(config["syntax"]["single_tags"])
    except KeyError as e:
      print(f"設定ファイルの形式が正しくありません。キーが不足しています: {e}")
      sys.exit(1)

    # DSL ファイルを UTF-8 で読み込み
    try:
      with open(args.input_file, "r", encoding="utf-8") as infile:
        dsl_code = infile.read()
    except Exception as e:
      print(f"入力ファイルの読み込みに失敗しました: {e}")
      sys.exit(1)

    # チェックを実行
    result = check_syntax(dsl_code, single_tags, group_tags)
    print("Syntax OK" if result else "Syntax Error")


if __name__ == "__main__":
  main()
