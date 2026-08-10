# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `To val {};`
- `std::istringstream ss {str.data()};`
- `const auto node {LoadYamlString(str)};`
- `std::list<T> vals;`
- `std::ostringstream ss;`
- `YAML::Node node;`
- `std::vector<T> vals;`
- `std::set<T> vals;`
- `std::unordered_set<T> vals;`
- `std::map<std::string, T> vals;`
- `std::ostringstream key;`
- `std::ostringstream val;`
- `std::unordered_map<std::string, T> vals;`
- `const std::shared_lock locker {mtx_};`
- `const std::unique_lock locker {mtx_};`
- `static std::uint64_t key {0};`
- `const auto var {Lookup<T>(name)};`
- `const auto new_var { std::make_shared<Var<T>>(name, default_val, description)};`
- `const auto base {LookupBase(name)};`
- `const auto var {std::dynamic_pointer_cast<Var<T>>(base)};`
- `std::list<std::pair<std::string, YAML::Node>> members;`
- `auto it {node.begin()};`
- `const auto key {ss.str()};`
- `auto sub_members {ExtractMembers( it->second, prefix.empty() ? key : prefix + "." + key)};`
- `const auto var {vars_.find(name.data())};`
- `const auto key {node.first};`
- `const auto var {LookupBase(key)};`
- `static const auto ins {std::make_shared<Config>("root")};`

## Exact top-level call expressions

- `static_cast<To>(val)`
- `to_string(val)`
- `val.data()`
- `str.data()`
- `ss.fail()`
- `fmt::format("Invalid value: '{}'", str)`
- `LoadYamlString(str)`
- `node.IsSequence()`
- `fmt::format("Mismatched type: '{}'", str)`
- `std::ranges::for_each(node, [&vals](const YAML::Node& child) { std::ostringstream ss; ss << child; vals.emplace_back(VarConverter<std::string, T> {}(ss.str())); })`
- `std::ranges::for_each(vals, [&node](const T& val) { node.push_back( LoadYamlString(VarConverter<T, std::string> {}(val))); })`
- `std::ranges::move(VarConverter<std::string, std::list<T>> {}(str), std::back_inserter(vals))`
- `VarConverter<std::list<T>, std::string> {}( {vals.cbegin(), vals.cend()})`
- `std::ranges::move(VarConverter<std::string, std::list<T>> {}(str), std::inserter(vals, vals.end()))`
- `node.IsMap()`
- `std::ranges::for_each( node, [&vals](const std::pair<YAML::Node, YAML::Node>& child) { std::ostringstream key; key << child.first; std::ostringstream val; val << child.second; vals.emplace(key.str(), VarConverter<std::string, T> {}(val.str())); })`
- `std::ranges::for_each( vals, [&node](const std::pair<std::string, T>& val) { node[val.first] = LoadYamlString(VarConverter<T, std::string> {}(val.second)); })`
- `std::ranges::move( VarConverter<std::string, std::map<std::string, T>> {}(str), std::inserter(vals, vals.end()))`
- `VarConverter<std::map<std::string, T>, std::string> {}( {vals.cbegin(), vals.cend()})`
- `ToStr {}(GetValue())`
- `SetValue(FromStr {}(str))`
- `std::ranges::for_each( listeners_, [&val, this](const auto& listener) noexcept { try { listener.second(val_, val); } catch (const std::exception& err) { std::osyncstream {std::cerr} << err.what() << std::endl; } })`
- `typeid(T).name()`
- `listeners_.erase(key)`
- `std::move(listener)`
- `listeners_.clear()`
- `Lookup<T>(name)`
- `std::make_shared<Var<T>>(name, default_val, description)`
- `vars_.emplace(name, new_var)`
- `LookupBase(name)`
- `std::dynamic_pointer_cast<Var<T>>(base)`
- `fmt::format("Mismatched type: '{}'", name)`
- `members.emplace_back(prefix, node)`
- `node.begin()`
- `node.end()`
- `ExtractMembers( it->second, prefix.empty() ? key : prefix + "." + key)`
- `members.merge( sub_members, [](const std::pair<std::string, YAML::Node>& lhs, const std::pair<std::string, YAML::Node>& rhs) noexcept { return lhs.first < rhs.first; })`
- `vars_.find(name.data())`
- `vars_.cend()`
- `ExtractMembers(root)`
- `key.empty()`
- `LookupBase(key)`
- `var->FromString(ss.str())`
- `std::ranges::for_each(vars_, [&visitor](const auto& var) noexcept { try { visitor(var.second); } catch (const std::exception& err) { std::osyncstream {std::cerr} << err.what() << std::endl; } })`
- `std::make_shared<Config>("root")`

# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `LoadYamlString`

### Exact declarations

- `YAML::Node LoadYamlString( std::string_view str, std::initializer_list<std::string_view> required_fields = {});`

### Exact target-source usages

- `LoadYamlString(str)`
- `LoadYamlString(VarConverter<T, std::string> {}(val))`
- `LoadYamlString(VarConverter<T, std::string> {}(val.second))`
