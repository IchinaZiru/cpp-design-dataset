# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `std::ifstream in{filename, std::ios::in | std::ios::binary};`
- `std::string content;`
- `const auto size = in.tellg();`
- `char buf[1 << 15];`
- `std::size_t n = 0;`
- `std::set<std::string> retval;`
- `const auto& sec = GetSection(section);`
- `const auto value = sec.find(name);`
- `const std::string value = Get(section, name);`
- `std::vector<T> vs;`
- `std::size_t i = 0;`
- `std::size_t j = i;`
- `T v{};`
- `static const std::unordered_map<std::string, bool> s2b{ {"1", true}, {"true", true}, {"yes", true}, {"on", true}, {"0", false}, {"false", false}, {"no", false}, {"off", false}, };`
- `const auto value = s2b.find(s);`
- `std::ostringstream ss;`
- `std::ostringstream oss;`
- `const auto sec = _values.find(section);`
- `const auto value = sec->second.find(name);`
- `constexpr std::string_view bom{"\xEF\xBB\xBF", 3};`
- `std::string section;`
- `std::unordered_map<std::string, std::string>* values = nullptr;`
- `int lineno = 0;`
- `const auto eol = content.find('\n');`
- `const auto line = detail::trim(content.substr(0, eol));`
- `const auto end = detail::find_char_or_comment(line.substr(1), "]");`
- `const auto sep = detail::find_char_or_comment(line, "=:");`
- `const auto name = detail::rtrim(line.substr(0, sep));`
- `auto value = line.substr(sep + 1);`
- `const auto comment = detail::find_char_or_comment(value, {});`

## Exact top-level call expressions

- `ParseError()`
- `in.seekg(0, std::ios::end)`
- `in.tellg()`
- `content.resize(static_cast<std::size_t>(size))`
- `in.seekg(0, std::ios::beg)`
- `in.read(&content[0], size)`
- `Parse(content)`
- `std::fread(buf, 1, sizeof(buf), file)`
- `content.append(buf, n)`
- `std::runtime_error("ini file not found.")`
- `std::runtime_error("memory alloc error")`
- `std::runtime_error("parse error on line no: " + std::to_string(_error))`
- `retval.insert(element.first)`
- `GetSection(section)`
- `sec.find(name)`
- `sec.end()`
- `std::runtime_error( "key '" + name + "' not found in section '" + section + "'.")`
- `BoolConverter(value->second)`
- `Converter<T>(value->second)`
- `Get<T>(section, name)`
- `std::forward<T>(default_v)`
- `Get(section, name)`
- `value.size()`
- `detail::is_space(value[i])`
- `detail::is_space(value[j])`
- `vs.emplace_back(Converter<T>(value.substr(i, j - i)))`
- `std::runtime_error("cannot parse value " + value + " to vector<T>.")`
- `GetVector<T>(section, name)`
- `_values[section].emplace(name, V2String(v))`
- `std::runtime_error("duplicate key '" + name + "' in section '" + section + "'.")`
- `_values[section].emplace(name, Vec2String(vs))`
- `FindEntry(section, name)`
- `detail::parse_value(s, v)`
- `std::runtime_error("cannot parse value '" + s + "' to type<T>.")`
- `s2b.find(s)`
- `s2b.end()`
- `std::runtime_error("'" + s + "' is not a valid boolean value.")`
- `ss.str()`
- `v.size()`
- `oss.str()`
- `_values.find(section)`
- `_values.end()`
- `std::runtime_error("section '" + section + "' not found.")`
- `sec->second.find(name)`
- `sec->second.end()`
- `std::runtime_error("key '" + name + "' not exist in section '" + section + "'.")`
- `content.substr(0, bom.size())`
- `content.remove_prefix(bom.size())`
- `content.empty()`
- `content.find('\n')`
- `detail::trim(content.substr(0, eol))`
- `content.remove_prefix(eol == std::string_view::npos ? content.size() : eol + 1)`
- `line.empty()`
- `line.front()`
- `detail::find_char_or_comment(line.substr(1), "]")`
- `section.assign(line.data() + 1, end)`
- `detail::find_char_or_comment(line, "=:")`
- `detail::rtrim(line.substr(0, sep))`
- `line.substr(sep + 1)`
- `detail::find_char_or_comment(value, {})`
- `value.substr(0, comment)`
- `detail::trim(value)`
- `values->emplace(std::string(name), std::string(value))`
- `std::runtime_error("duplicate key '" + std::string(name) + "' in section '" + section + "'.")`
