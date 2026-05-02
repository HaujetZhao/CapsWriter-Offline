这是作者的 Python 正则表达式学习笔记，比较全面，可以辅助编写正则规则。

## 一、正则表达式语法

在线工具：

- [regex101: build, test, and debug regex](https://regex101.com/) 
- [Debuggex: Online visual regex tester. JavaScript, Python, and PCRE.](https://www.debuggex.com/?flavor=javascript) 
- [Regular-Expressions.info - Regex Tutorial, Examples and Reference - Regexp Patterns](https://www.regular-expressions.info/) 

### （一） 字符与字符类

#### 特殊字符

`\.^$?+*{}[]()|` 为特殊字符，若想要使用字面值，必须使用 `\` 进行转义

#### 字符类 `[]` 

 `[]` 匹配包含在方括号中的任何字符。它也可以指定范围，例：

   - `[a-zA-Z0-9]`表示a到z，A到Z，0到9之间的任何一个字符
   - `[\u4e00-\u9fa5]` 匹配 Unicode 中文
   - `[^\x00-\xff]` 匹配双字节字符（包括中文）

 在 `[]` 中：

   - `[^]` 表示否定字符类，比如`[^0-9]`表示可以匹配一个任意非数字的字符
   - `^` 放在第一个位置表示否定，放在其他位置表示字面值
   - `\` 表示转义
   - `-` 放在中间表示范围，放在其他位置表示字面值
   - 其他特殊字符不再具备特殊意义，都表示字面值
   - 字符类内部可以使用速记法，比如`\d \s \w` 

#### 速记法

- `.` 可以匹配除换行符之外的任何字符，如果有 re.DOTALL 标志，则匹配任意字符包括换行
- `\d`  匹配一个 Unicode 数字，如果有 re.ASCII 标志，则匹配0-9
- `\D` 匹配 Unicode 非数字
- `\s`  匹配 Unicode 空白，如果带有 re.ASCII 标志，则匹配`\t\n\r\f\v`中的一个
- `\S` 匹配 Unicode 非空白
- `\w`  匹配 Unicode 单词字符，如果带有 re.ASCII 标志,则匹配`[a-zA-Z0-9_]`中的一个
- `\W` 匹配 Unicode 非单词字符


### （二）量词

- `?`      0次或1次
- `*`      0次或多次
- `+`      1次或者多次
- `{m}`     m次
- `{m,}`   至少m次
- `{,n}`    最多n次
- `{m,n}`  至少m次，最多n次

注意点：以上量词都是「贪婪模式」，后加 `?` 切换为「最小匹配模式」

### （三） 断言

断言不会匹配任何文本，只是施加约束。常用断言：

- `\b`匹配单词的边界，放在字符类 `[]` 中则表示 `backspace`
- `\B`匹配非单词边界，受ASCII标记影响
- `\A` 在起始处匹配
- `\Z` 在结尾处匹配
- `^`  在起始处匹配，如果有 MULTILINE 标志，则在每个换行符后匹配
- `$`   在结尾处匹配，如果有 MULTILINE 标志，则在每个换行符前匹配

### （四）捕获组

`()`的作用：

- `()`是一个捕获组，可被 `\N` 引用，`N` 是序号，以左括号排位决定。`\0` 表示整个匹配的内容。
- `(?:)` 可以关闭捕获，只用作分组
- 使用 `|` 组合多个表达式，表示「或」
- `(?=...)` 向前正项匹配，前方必须存在。 如`\w+(?=,)` 匹配 `apple, banana` 中的 `apple`
- `(?!...)` 向前负项匹配，前方必须没有
- `(?<=...)` 向后正项匹配，后方必须存在
- `(?<!...)` 向后负项匹配，后方必须没有

命名捕获组：

| 语言                                                         | 命名捕获组                  | 搜索中引用                                                   | 替换中引用         |
| ------------------------------------------------------------ | --------------------------- | ------------------------------------------------------------ | ------------------ |
| [Python](https://docs.python.org/3/howto/regex.html#non-capturing-and-named-groups) | `(?P<name>...)`             | `\N (?P=name)`                                               | `\N \g<name> $N`   |
| [JavaScript](https://javascript.info/regexp-backreferences)  | `(?<name>...)`              | `\N \k<name>`                                                | `$N $<name>`       |
| [.NET](https://learn.microsoft.com/en-us/dotnet/standard/base-types/backreference-constructs-in-regular-expressions) | `(?<name>...) (?'name'...)` | `\N \k<name> \k'name'`                                       | `$N ${N} ${name}`  |
| [Perl](https://perldoc.perl.org/perlre#Capture-groups)       | `(?<name>...) (?'name'...)` | `\N \gN \g{N} \g{name}`  <br />`(?N) (?+N) (?-N) (?Name)`<br />兼容 `.Net Python` 的语法 | `$N ${N} $+{Name}` |

技巧：

- 在搜索中，若 `\12` 无法表示「第一个捕获组 + 数字2」，可用 `(?:\1)2` 或者 `\1[2]` 表示
- 在替换中，若 `$12` 无法表示「第一个捕获组 + 数字2」，可以用 `$1\l2` 或者 `$1\u2` 表示

### （五）条件匹配

- `(?(id)yes_exp|no_exp)`：对应 `id` 的子表达式如果匹配到内容，则这里匹配 `yes_exp`，否则匹配 `no_exp` 
- Perl 支持的语法：`(?(N)Yes|No) (?(<Name>)Yes|No) (?('Name')Yes|No) (?(?=Ahead)Yes|No)` 

> 实测 JavaScript 不支持条件匹配

### （六）替换语法补充

一些在替换中使用的语法：

| 替换语法 | 作用               |
| -------- | ------------------ |
| `\l`     | 下一个字符输出小写 |
| `\L`     | 下一串字符输出小写 |
| `\u`     | 下一个字符输出大写 |
| `\U`     | 下一串字符输出大写 |
| `\E`     | 终止 `\U` 和 `\L`  |

| 语言                                                        | 引用匹配之前的文本 | 引用匹配文本 | 引用匹配之后的文本 |
| ----------------------------------------------------------- | ------------------ | ------------ | ------------------ |
| [Perl](https://perldoc.perl.org/perlre#Regular-Expressions) | `${^PREMATCH}`     | `${^MATCH}`  | `${^POSTMATCH}`    |

### （七）  标志

传标志方法：

- 正则表达式开头加标志 `(?flags)pattern` ，如 `(?im)apple` 表示不区分大小写
  - `i` 或 `IGNORECASE`：忽略大小写，使匹配不区分大小写。
  - `m` 或 `MULTILINE`：启用多行模式
  - `s` 或 `DOTALL`：启用点字符（`.`）匹配任意字符，包括换行符。`s` 是 `special` 的缩写。
  - `x` 或 `VERBOSE`：启用详细模式，忽略空格和注释，可以使用多行形式编写更易读的正则表达式。可以用 `[ ] \x20 (?-x: )` 表示空格。`x` 是 `extended` 缩写
  - `g` 或 `GLOBAL`: 查找所有符合条件的结果（Python 中不需要）
- python 中 re.compile 的 flags 参数。flags 实质是一个数字，可以用 `|` 按位与传入多个标志
  - `re.A` 或 `re.ASCII`
  - `re.I` 或 `re.IGNORECASE`
  - `re.M` 或 `re.MULTILINE`
  - `re.S` 或 `re.DOTALL`
  - `re.X` 或 `re.VERBOSE` 

注释示例，匹配 `<img>` 标签：

```python
pattern = re.compile(r"""(?ix)          # i 表示忽略大小写，x 表示开启注释模式
        <img\s+                         #标签的开始
            [^>]*?                      #不是src的属性
            src=                        #src属性的开始
                (?P<quote>["'])         #左引号
                (?P<image_name>[^"'<>]+?)  #图片名字
                (?P=quote)              #右括号
            [^>]*?                      #不是src的属性
        >                               #标签的结束
    """)
```

### （八）缩写释义

为什么 `.Net` 用 `\k<name>` 引用捕获组，其中的 `k` 表示什么？世界上所有的规范中，字母的选取都是很讲究的，很少有无缘无故的字母标志，它们往往是一些单词的缩写。了解这些缩写，对于记住语法会很有帮助。

在这里，我推测 `k` 表示 `key`。

| 缩写 | 全拼           |
| ---- | -------------- |
| a    | ascii          |
| b    | border         |
| d    | digit          |
| e    | end            |
| g    | global, group  |
| i    | ignore         |
| k    | key            |
| l    | lower          |
| m    | multiline      |
| p    | python         |
| s    | space, special |
| u    | upper          |
| w    | word           |
| x    | extend         |



## 二、[Python正则表达式模块](https://docs.python.org/3/library/re.html) 

模块级 ：

| 方法、属性                             | 作用                                                         |
| -------------------------------------- | ------------------------------------------------------------ |
| `compile(pattern)`                     | 预先编译正则表达式，返回 `re.Pattern` 对象                   |
| `search(pattern, string, flags=0)`     | 查找匹配的部分，返回 `re.Match`                              |
| `match(pattern, string, flags=0)`      | 从头匹配，返回符合规则的第一个值 `re.Match`                  |
| `fullmatch(pattern, string, flags=0)`  | 完全匹配（要从头到尾都匹配），返回 `re.Match`                |
| `split(pattern, string, maxsplit=0)`   | 用匹配到的内容作为分割符，分割后，返回列表                   |
| `findall(pattern, string)`             | 查找所有，返回为列表，元素为 str。如果有捕获组，则列表元素为 tuple，包含空结果。 |
| `finditer(pattern, string)`            | 查找所有，返回为  `re.Match` 的迭代器。                      |
| `sub(pattern, repl, string, count=0)`  | 返回替换后的字符串，`repl` 可以是一个函数（接收 `Match`，返回替换后的值） |
| `subn(pattern, repl, string, count=0)` | 返回元组 `(new_str, number)`，包含了替换次数                 |
| `escape(pattern)`                      | 将特殊字符转义后返回，如 `.` 会返回 `\.`                     |
| `purge()`                              | 清除缓存                                                     |

`re.compile()` 可以预先编译正则表达式，返回 `re.Pattern` 对象，以提高匹配效率

| 方法、属性                            | 作用                                                         |
| ------------------------------------- | ------------------------------------------------------------ |
| `.search(string[, pos[, endpos]])`    | 查找匹配的部分，返回 `re.Match`，`pos` 和 `endpos` 限制查找区间 |
| `.match(string[, pos[, endpos]])`     |                                                              |
| `.fullmatch(string[, pos[, endpos]])` |                                                              |
| `.split(string, maxsplit=0)`          |                                                              |
| `.findall()`                          |                                                              |
| `.finditer()`                         |                                                              |
| `.sub(repl, string, count=0)`         |                                                              |
| `.subn(repl, string, count=0)`        |                                                              |
| `.flags`                              |                                                              |
| `.groups`                             | 有几个捕获组                                                 |
| `.groupindex`                         | 一个字典，命名捕获组与序号对应                               |
| `.pattern`                            |                                                              |

`re.Match` 对象用于表示正则表达式匹配的结果：

| 方法、属性                   | 作用                                                         |
| ---------------------------- | ------------------------------------------------------------ |
| `Match.group([group1, ...])` | 返回：捕获组，或多个捕获组 tuple                             |
| `Match[0]`                   | 等同于 `group(0)`                                            |
| `.group()`                   | 等同于 `group(0)`                                            |
| `.groups(default=None)`      | 返回：元组，所有的子捕获组 (1, 2, 3...)。没有捕获到的组返回为 None。 |
| `.groupdict(default=None)`   | 返回：词典，只包含有命名的捕获组                             |
| `.start()`                   | 返回：匹配的起始位置                                         |
| `.end()`                     | 返回：匹配的结束位置                                         |
| `.span()`                    | 返回：元组 (start, end)                                      |
| `.expand(template)`          | 用捕获到的组将 `template` 中的组引用展开                     |
| `.pos`                       | 匹配开始的索引位置                                           |
| `.endpos`                    | 匹配结束的索引位置                                           |
| `.lastindex`                 | 最后一个捕获组的索引                                         |
| `.lastgroup`                 | 最后一个捕获组的名字                                         |
| `.string`                    | 传入的字符串                                                 |

