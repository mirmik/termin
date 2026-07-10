#include <algorithm>
#include <atomic>
#include <cctype>
#include <filesystem>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <system_error>
#include <thread>
#include <tuple>
#include <utility>
#include <vector>

#include <clang/AST/DeclCXX.h>
#include <clang/AST/DeclTemplate.h>
#include <clang/AST/RecursiveASTVisitor.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/FrontendActions.h>
#include <clang/Tooling/ArgumentsAdjusters.h>
#include <clang/Tooling/CompilationDatabase.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/Support/CommandLine.h>
#include <llvm/Support/JSON.h>
#include <llvm/Support/raw_ostream.h>

namespace {

namespace fs = std::filesystem;

llvm::cl::OptionCategory checker_category("termin-cpp-class-layout options");

llvm::cl::opt<std::string> build_path(
    "p",
    llvm::cl::desc("Build directory containing compile_commands.json"),
    llvm::cl::value_desc("build-path"),
    llvm::cl::Required,
    llvm::cl::cat(checker_category)
);

llvm::cl::opt<std::string> repo_root_option(
    "repo-root",
    llvm::cl::desc("Repository root used for ownership and relative paths"),
    llvm::cl::value_desc("path"),
    llvm::cl::init("."),
    llvm::cl::cat(checker_category)
);

llvm::cl::opt<std::string> output_format(
    "format",
    llvm::cl::desc("Output format: text or jsonl"),
    llvm::cl::value_desc("format"),
    llvm::cl::init("text"),
    llvm::cl::cat(checker_category)
);

llvm::cl::opt<bool> no_fail(
    "no-fail",
    llvm::cl::desc("Return success when layout violations are found"),
    llvm::cl::init(false),
    llvm::cl::cat(checker_category)
);

llvm::cl::opt<unsigned> jobs(
    "jobs",
    llvm::cl::desc("Number of translation units to analyze in parallel"),
    llvm::cl::value_desc("count"),
    llvm::cl::init(1),
    llvm::cl::cat(checker_category)
);

llvm::cl::list<std::string> path_filters(
    "path",
    llvm::cl::desc("Only report declarations below this repository-relative path"),
    llvm::cl::value_desc("path"),
    llvm::cl::ZeroOrMore,
    llvm::cl::cat(checker_category)
);

llvm::cl::list<std::string> extra_excludes(
    "exclude-path",
    llvm::cl::desc("Exclude a repository-relative path (may be repeated)"),
    llvm::cl::value_desc("path"),
    llvm::cl::ZeroOrMore,
    llvm::cl::cat(checker_category)
);

struct SourcePoint {
    unsigned line = 0;
    unsigned column = 0;
};

struct MisplacedField {
    std::string name;
    std::string kind;
    SourcePoint point;
    bool macro_expansion = false;
};

struct Violation {
    std::string file;
    std::string class_name;
    SourcePoint class_point;
    std::string first_method;
    SourcePoint method_point;
    std::vector<MisplacedField> fields;
};

fs::path normalized_absolute(const fs::path& value) {
    std::error_code error;
    fs::path absolute = value.is_absolute() ? value : fs::absolute(value, error);
    if (error) {
        return value.lexically_normal();
    }

    fs::path canonical = fs::weakly_canonical(absolute, error);
    return error ? absolute.lexically_normal() : canonical;
}

std::string normalized_relative_option(std::string_view value) {
    fs::path path(value);
    std::string normalized = path.lexically_normal().generic_string();
    while (normalized.starts_with("./")) {
        normalized.erase(0, 2);
    }
    while (!normalized.empty() && normalized.back() == '/') {
        normalized.pop_back();
    }
    return normalized;
}

bool is_path_prefix(std::string_view prefix, std::string_view value) {
    if (prefix.empty() || prefix == ".") {
        return true;
    }
    if (value == prefix) {
        return true;
    }
    return value.size() > prefix.size() && value.starts_with(prefix) &&
           value[prefix.size()] == '/';
}

class Report {
  private:
    fs::path repo_root_;
    std::vector<std::string> filters_;
    std::vector<std::string> excludes_;
    std::mutex mutex_;
    std::set<std::string> seen_definitions_;
    std::vector<Violation> violations_;

  public:
    explicit Report(fs::path repo_root)
        : repo_root_(normalized_absolute(repo_root)) {
        for (const std::string& value : path_filters) {
            filters_.push_back(normalized_relative_option(value));
        }
        for (const std::string& value : extra_excludes) {
            excludes_.push_back(normalized_relative_option(value));
        }
    }

    std::optional<std::string> owned_relative_path(
        llvm::StringRef filename,
        bool apply_path_filters = true
    ) const {
        if (filename.empty()) {
            return std::nullopt;
        }

        fs::path absolute = normalized_absolute(filename.str());
        std::error_code error;
        fs::path relative_path = fs::relative(absolute, repo_root_, error);
        if (error || relative_path.empty()) {
            return std::nullopt;
        }

        std::string relative = relative_path.lexically_normal().generic_string();
        if (relative == ".." || relative.starts_with("../")) {
            return std::nullopt;
        }

        static const std::set<std::string> excluded_components = {
            ".git",
            "build",
            "sdk",
            "termin-thirdparty",
        };
        for (const fs::path& component : relative_path) {
            if (excluded_components.contains(component.string())) {
                return std::nullopt;
            }
        }

        for (const std::string& exclude : excludes_) {
            if (is_path_prefix(exclude, relative)) {
                return std::nullopt;
            }
        }

        if (apply_path_filters && !filters_.empty()) {
            bool matches = std::ranges::any_of(filters_, [&](const std::string& filter) {
                return is_path_prefix(filter, relative);
            });
            if (!matches) {
                return std::nullopt;
            }
        }

        return relative;
    }

    bool mark_seen(const std::string& key) {
        std::lock_guard lock(mutex_);
        return seen_definitions_.insert(key).second;
    }

    void add(Violation violation) {
        std::lock_guard lock(mutex_);
        violations_.push_back(std::move(violation));
    }

    void sort() {
        std::ranges::sort(violations_, [](const Violation& left, const Violation& right) {
            return std::tie(left.file, left.class_point.line, left.class_point.column,
                            left.class_name) <
                   std::tie(right.file, right.class_point.line, right.class_point.column,
                            right.class_name);
        });
    }

    const std::vector<Violation>& violations() const {
        return violations_;
    }
};

SourcePoint source_point(const clang::SourceManager& source_manager,
                         clang::SourceLocation location) {
    clang::SourceLocation expansion = source_manager.getExpansionLoc(location);
    clang::PresumedLoc presumed = source_manager.getPresumedLoc(expansion);
    if (presumed.isInvalid()) {
        return {};
    }
    return {presumed.getLine(), presumed.getColumn()};
}

std::string declaration_name(const clang::NamedDecl& declaration,
                             std::string_view fallback) {
    std::string name = declaration.getNameAsString();
    return name.empty() ? std::string(fallback) : name;
}

struct DataMemberInfo {
    const clang::Decl* declaration = nullptr;
    std::string name;
    std::string kind;
};

std::optional<DataMemberInfo> data_member_info(const clang::Decl& declaration) {
    if (const auto* field = llvm::dyn_cast<clang::FieldDecl>(&declaration)) {
        return DataMemberInfo{
            field,
            declaration_name(*field, "<anonymous field>"),
            field->isBitField() ? "bit-field" : "field",
        };
    }

    if (const auto* variable = llvm::dyn_cast<clang::VarDecl>(&declaration);
        variable != nullptr && variable->isStaticDataMember()) {
        return DataMemberInfo{
            variable,
            declaration_name(*variable, "<anonymous static field>"),
            "static-field",
        };
    }

    if (const auto* indirect = llvm::dyn_cast<clang::IndirectFieldDecl>(&declaration)) {
        return DataMemberInfo{
            indirect,
            declaration_name(*indirect, "<anonymous field>"),
            "indirect-field",
        };
    }

    if (const auto* record = llvm::dyn_cast<clang::RecordDecl>(&declaration);
        record != nullptr && record->isAnonymousStructOrUnion()) {
        return DataMemberInfo{
            record,
            record->isUnion() ? "<anonymous union>" : "<anonymous struct>",
            record->isUnion() ? "anonymous-union" : "anonymous-struct",
        };
    }

    return std::nullopt;
}

const clang::CXXMethodDecl* method_info(const clang::Decl& declaration) {
    if (const auto* method = llvm::dyn_cast<clang::CXXMethodDecl>(&declaration)) {
        return method;
    }

    if (const auto* function_template =
            llvm::dyn_cast<clang::FunctionTemplateDecl>(&declaration)) {
        return llvm::dyn_cast<clang::CXXMethodDecl>(
            function_template->getTemplatedDecl()
        );
    }

    return nullptr;
}

class ClassLayoutVisitor : public clang::RecursiveASTVisitor<ClassLayoutVisitor> {
  private:
    clang::SourceManager& source_manager_;
    Report& report_;

  public:
    ClassLayoutVisitor(clang::ASTContext& context, Report& report)
        : source_manager_(context.getSourceManager()), report_(report) {}

    bool VisitCXXRecordDecl(clang::CXXRecordDecl* record) {
        if (record == nullptr || record->isImplicit() || record->isLambda() ||
            !record->isThisDeclarationADefinition()) {
            return true;
        }

        if (record->getTemplateSpecializationKind() == clang::TSK_ImplicitInstantiation) {
            return true;
        }

        clang::SourceLocation record_location =
            source_manager_.getExpansionLoc(record->getBeginLoc());
        auto relative_file = report_.owned_relative_path(
            source_manager_.getFilename(record_location)
        );
        if (!relative_file.has_value()) {
            return true;
        }

        std::string class_name = record->getQualifiedNameAsString();
        SourcePoint class_point = source_point(source_manager_, record_location);
        if (class_name.empty()) {
            class_name = "<anonymous@" + std::to_string(class_point.line) + ">";
        }

        std::string definition_key = *relative_file + ":" +
                                     std::to_string(class_point.line) + ":" +
                                     std::to_string(class_point.column) + ":" + class_name;
        if (!report_.mark_seen(definition_key)) {
            return true;
        }

        const clang::CXXMethodDecl* first_method = nullptr;
        std::vector<MisplacedField> misplaced_fields;

        for (const clang::Decl* member : record->decls()) {
            if (member == nullptr || member->isImplicit() ||
                member->getLexicalDeclContext() != record) {
                continue;
            }

            if (first_method == nullptr) {
                first_method = method_info(*member);
                if (first_method != nullptr) {
                    continue;
                }
            }

            if (first_method == nullptr) {
                continue;
            }

            std::optional<DataMemberInfo> field = data_member_info(*member);
            if (!field.has_value()) {
                continue;
            }

            clang::SourceLocation field_location = field->declaration->getBeginLoc();
            misplaced_fields.push_back({
                std::move(field->name),
                std::move(field->kind),
                source_point(source_manager_, field_location),
                field_location.isMacroID(),
            });
        }

        if (first_method == nullptr || misplaced_fields.empty()) {
            return true;
        }

        report_.add({
            *relative_file,
            std::move(class_name),
            class_point,
            declaration_name(*first_method, "<anonymous method>"),
            source_point(source_manager_, first_method->getBeginLoc()),
            std::move(misplaced_fields),
        });
        return true;
    }

};

class ClassLayoutConsumer : public clang::ASTConsumer {
  private:
    ClassLayoutVisitor visitor_;

  public:
    ClassLayoutConsumer(clang::ASTContext& context, Report& report)
        : visitor_(context, report) {}

    void HandleTranslationUnit(clang::ASTContext& context) override {
        visitor_.TraverseDecl(context.getTranslationUnitDecl());
    }

};

class ClassLayoutAction : public clang::ASTFrontendAction {
  private:
    Report& report_;

  public:
    explicit ClassLayoutAction(Report& report) : report_(report) {}

    std::unique_ptr<clang::ASTConsumer> CreateASTConsumer(
        clang::CompilerInstance& compiler,
        llvm::StringRef
    ) override {
        return std::make_unique<ClassLayoutConsumer>(compiler.getASTContext(), report_);
    }

};

class ClassLayoutActionFactory : public clang::tooling::FrontendActionFactory {
  private:
    Report& report_;

  public:
    explicit ClassLayoutActionFactory(Report& report) : report_(report) {}

    std::unique_ptr<clang::FrontendAction> create() override {
        return std::make_unique<ClassLayoutAction>(report_);
    }

};

void print_text_report(const std::vector<Violation>& violations) {
    for (const Violation& violation : violations) {
        const MisplacedField& first_field = violation.fields.front();
        llvm::outs() << violation.file << ':' << first_field.point.line << ':'
                     << first_field.point.column
                     << ": error: class '" << violation.class_name
                     << "' declares data members after member function '"
                     << violation.first_method
                     << "' [termin-cpp-class-layout]\n";
        llvm::outs() << "  misplaced fields:";
        for (const MisplacedField& field : violation.fields) {
            llvm::outs() << ' ' << field.name << "@" << field.point.line;
            if (field.macro_expansion) {
                llvm::outs() << "(macro)";
            }
        }
        llvm::outs() << '\n';
    }
}

void print_jsonl_report(const std::vector<Violation>& violations) {
    for (const Violation& violation : violations) {
        llvm::json::Array fields;
        for (const MisplacedField& field : violation.fields) {
            fields.push_back(llvm::json::Object{
                {"name", field.name},
                {"kind", field.kind},
                {"line", field.point.line},
                {"column", field.point.column},
                {"macro_expansion", field.macro_expansion},
            });
        }

        llvm::json::Object value{
            {"file", violation.file},
            {"class", violation.class_name},
            {"line", violation.class_point.line},
            {"column", violation.class_point.column},
            {"first_method", llvm::json::Object{
                {"name", violation.first_method},
                {"line", violation.method_point.line},
                {"column", violation.method_point.column},
            }},
            {"misplaced_fields", std::move(fields)},
        };

        llvm::json::OStream stream(llvm::outs(), 0);
        stream.value(std::move(value));
        llvm::outs() << '\n';
    }
}

bool is_cxx_source(llvm::StringRef filename) {
    std::string extension = fs::path(filename.str()).extension().string();
    std::ranges::transform(extension, extension.begin(), [](unsigned char value) {
        return static_cast<char>(std::tolower(value));
    });
    static const std::set<std::string> cxx_extensions = {
        ".cc",
        ".cpp",
        ".cxx",
        ".c++",
        ".mm",
    };
    return cxx_extensions.contains(extension);
}

int analyze_sources(
    const clang::tooling::CompilationDatabase& database,
    const std::vector<std::string>& source_files,
    Report& report
) {
    std::atomic<size_t> next_source = 0;
    std::atomic<int> result = 0;
    size_t worker_count = std::min<size_t>(jobs, source_files.size());
    std::vector<std::thread> workers;
    workers.reserve(worker_count);

    for (size_t remaining_workers = worker_count;
         remaining_workers > 0;
         --remaining_workers) {
        workers.emplace_back([&] {
            while (true) {
                size_t source_index = next_source.fetch_add(1);
                if (source_index >= source_files.size()) {
                    return;
                }

                clang::tooling::ClangTool tool(
                    database,
                    {source_files[source_index]}
                );
                tool.appendArgumentsAdjuster(
                    clang::tooling::getClangStripOutputAdjuster()
                );
                tool.appendArgumentsAdjuster(
                    clang::tooling::getClangSyntaxOnlyAdjuster()
                );
                tool.appendArgumentsAdjuster(
                    clang::tooling::getInsertArgumentAdjuster(
                        "-Wno-unknown-warning-option",
                        clang::tooling::ArgumentInsertPosition::END
                    )
                );

                ClassLayoutActionFactory factory(report);
                if (tool.run(&factory) != 0) {
                    result.store(1);
                }
            }
        });
    }

    for (std::thread& worker : workers) {
        worker.join();
    }
    return result.load();
}

} // namespace

int main(int argc, const char** argv) {
    llvm::cl::HideUnrelatedOptions(checker_category);
    llvm::cl::ParseCommandLineOptions(
        argc,
        argv,
        "Check that C++ data members are declared before member functions.\n"
    );

    if (output_format != "text" && output_format != "jsonl") {
        llvm::errs() << "error: --format must be 'text' or 'jsonl'\n";
        return 2;
    }

    std::string database_error;
    std::unique_ptr<clang::tooling::CompilationDatabase> database =
        clang::tooling::CompilationDatabase::autoDetectFromDirectory(
            build_path,
            database_error
        );
    if (database == nullptr) {
        llvm::errs() << "error: failed to load compilation database from '"
                     << build_path << "': " << database_error << '\n';
        return 2;
    }

    if (jobs == 0) {
        llvm::errs() << "error: --jobs must be greater than zero\n";
        return 2;
    }

    std::vector<std::string> database_files = database->getAllFiles();
    if (database_files.empty()) {
        llvm::errs() << "error: compilation database contains no source files\n";
        return 2;
    }

    Report report(fs::path(repo_root_option.getValue()));
    std::vector<std::string> source_files;
    for (const std::string& source : database_files) {
        if (!is_cxx_source(source)) {
            continue;
        }
        if (!report.owned_relative_path(source, false).has_value()) {
            continue;
        }
        source_files.push_back(source);
    }

    if (source_files.empty()) {
        llvm::errs() << "termin-cpp-class-layout: 0 matching C++ translation units\n";
        return 0;
    }

    llvm::errs() << "termin-cpp-class-layout: analyzing " << source_files.size()
                 << " C++ translation unit(s) with "
                 << std::min<size_t>(jobs, source_files.size()) << " job(s)\n";

    int tool_result = analyze_sources(*database, source_files, report);
    if (tool_result != 0) {
        llvm::errs() << "error: Clang failed while analyzing the compilation database\n";
        return 2;
    }

    report.sort();
    if (output_format == "jsonl") {
        print_jsonl_report(report.violations());
    } else {
        print_text_report(report.violations());
    }
    llvm::outs().flush();

    llvm::errs() << "termin-cpp-class-layout: " << report.violations().size()
                 << " class violation(s)\n";

    if (!report.violations().empty() && !no_fail) {
        return 1;
    }
    return 0;
}
