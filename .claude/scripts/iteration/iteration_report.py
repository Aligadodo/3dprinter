"""iteration_report.py - Generate iteration summary report."""
import json
import os
import glob
import re
import subprocess
import sys
from datetime import datetime

# Force UTF-8 on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CODE_EXTS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.css', '.scss', '.html', '.jinja', '.jinja2'}
TEST_DIRS = {'tests', 'test'}
IGNORE_PATTERNS = ['.claude/', 'docs/', 'iterations/']


def _is_code_file(filepath):
    """Check if a file is application code (not docs/config/scripts/hooks)."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in CODE_EXTS:
        return False
    for pat in IGNORE_PATTERNS:
        if filepath.startswith(pat) or ('/' + pat) in filepath or ('\\' + pat) in filepath:
            return False
    # Exclude test files themselves
    parts = filepath.replace('\\', '/').split('/')
    for part in parts:
        if part in TEST_DIRS:
            return False
    return True


def _has_code_changes(all_changed):
    """Return True if any changed file is application code."""
    return any(_is_code_file(f) for f in all_changed)


def _run_tests(project_dir, timeout=180):
    """Run pytest and return (passed, failed, errors, skipped, output_lines)."""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=short'],
            capture_output=True, text=True, timeout=timeout,
            cwd=project_dir,
            env={**os.environ, 'PYTHONPATH': project_dir,
                 'PYTHONUNBUFFERED': '1'}
        )
        output = (result.stdout + '\n' + result.stderr).strip()
        lines = output.split('\n')

        # Parse pytest short summary: "28 passed, 14 errors"
        passed = failed = errors = skipped = 0
        summary_line = ''
        for line in reversed(lines):
            if re.search(r'\d+\s+(passed|failed|error)', line):
                summary_line = line
                break

        m = re.search(r'(\d+)\s+passed', summary_line)
        if m:
            passed = int(m.group(1))
        m = re.search(r'(\d+)\s+failed', summary_line)
        if m:
            failed = int(m.group(1))
        m = re.search(r'(\d+)\s+errors?', summary_line)
        if m:
            errors = int(m.group(1))
        m = re.search(r'(\d+)\s+skipped', summary_line)
        if m:
            skipped = int(m.group(1))

        return passed, failed, errors, skipped, lines
    except subprocess.TimeoutExpired:
        return 0, 0, 0, 0, ['TIMEOUT: tests did not complete within %ds' % timeout]
    except Exception as e:
        return 0, 0, 0, 0, ['ERROR running tests: %s' % str(e)]


def run_git(project_dir, args):
    try:
        return subprocess.check_output(
            ['git', '-C', project_dir] + args,
            stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return ''


def _storage_dirs(base_dir):
    """Resolve iteration/report storage paths.
    Git-tracked project → <project>/docs/iterations/
    Claude home fallback → ~/.claude/iterations/ and ~/.claude/reports/
    """
    claude_home = os.path.join(os.path.expanduser('~'), '.claude')
    if os.path.normpath(base_dir) == os.path.normpath(claude_home):
        return (os.path.join(base_dir, 'iterations'),
                os.path.join(base_dir, 'reports'))
    return (os.path.join(base_dir, 'docs', 'iterations'),
            os.path.join(base_dir, 'docs', 'iterations'))


def _update_index(iterations_dir, report_filename, title):
    """Add entry to top of INDEX.md (newest first), creating it if needed."""
    import re
    index_path = os.path.join(iterations_dir, 'INDEX.md')
    today = datetime.now().strftime('%Y-%m-%d')
    new_entry = f'- [{today}] [{title}]({report_filename})'

    existing_entries = []
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if re.match(r'^- \[', line):
                    existing_entries.append(line)

    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('# Iteration History\n\nSorted by time (newest first).\n\n')
        f.write(new_entry + '\n')
        for entry in existing_entries:
            f.write(entry + '\n')


def main():
    project_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    iteration_dir, reports_dir = _storage_dirs(project_dir)
    os.makedirs(iteration_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    now = datetime.now()
    report_filename = now.strftime('%Y-%m-%d-%H%M%S-report.md')
    report_file = os.path.join(reports_dir, report_filename)

    # Find most recent iteration start (or use explicit file from env)
    start_data = None
    explicit_start = os.environ.get('ITERATION_START_FILE', '')
    if explicit_start and os.path.exists(explicit_start):
        with open(explicit_start, 'r', encoding='utf-8') as f:
            start_data = json.load(f)
    else:
        start_files = sorted(
            glob.glob(os.path.join(iteration_dir, '*-start.json')),
            key=os.path.getmtime, reverse=True
        )
        if start_files:
            with open(start_files[0], 'r', encoding='utf-8') as f:
                start_data = json.load(f)

    # Current git status
    has_git = os.path.isdir(os.path.join(project_dir, '.git'))

    current_branch = run_git(project_dir, ['rev-parse', '--abbrev-ref', 'HEAD']) if has_git else ''
    current_commit = run_git(project_dir, ['log', '-1', '--format=%h %s']) if has_git else ''

    all_changed = []
    staged_files = []
    diff_stat = ''

    if has_git:
        diff_stat = run_git(project_dir, ['diff', '--stat', 'HEAD'])
        changed_raw = run_git(project_dir, ['diff', '--name-only', 'HEAD']).split('\n')
        all_changed = [f for f in changed_raw if f]
        staged_raw = run_git(project_dir, ['diff', '--cached', '--name-only']).split('\n')
        staged_files = [f for f in staged_raw if f]

    # Categorize changes
    categories = {}
    for f in all_changed:
        ext = os.path.splitext(f)[1] or 'config'
        if 'test' in f.lower() or 'spec' in f.lower():
            cat = 'test'
        elif ext in ['.py']:
            cat = 'backend'
        elif ext in ['.html', '.css', '.js', '.jsx', '.tsx', '.ts', '.vue']:
            cat = 'frontend'
        elif ext in ['.md', '.txt', '.rst']:
            cat = 'docs'
        elif ext in ['.yaml', '.yml', '.json', '.toml', '.ini', '.cfg']:
            cat = 'config'
        elif ext in ['.sh', '.ps1', '.bat']:
            cat = 'scripts'
        else:
            cat = 'other'
        categories[cat] = categories.get(cat, 0) + 1

    # Plan progress — try start.json first, then fall back to plan file directly
    plan_progress = None
    plan_content = ""
    if start_data and start_data.get('plan'):
        p = start_data['plan']
        plan_progress = {
            'name': p['name'],
            'tasks_total': p['tasks_total'],
            'tasks_done_start': p['tasks_done'],
        }

    # If no start.json, try to read the active plan file for context
    if not plan_progress:
        plans_dir = os.path.join(os.path.expanduser('~'), '.claude', 'plans')
        if os.path.isdir(plans_dir):
            plan_files = sorted(
                [f for f in glob.glob(os.path.join(plans_dir, '*.md'))],
                key=os.path.getmtime, reverse=True
            )
            if plan_files:
                plan_name = os.path.basename(plan_files[0]).replace('.md', '')
                with open(plan_files[0], 'r', encoding='utf-8') as f:
                    plan_content = f.read()
                # Count tasks from plan
                task_lines = [l for l in plan_content.split('\n')
                            if l.strip().startswith('- [')]
                total = len(task_lines)
                done = sum(1 for l in task_lines if l.strip().startswith('- [x]'))
                plan_progress = {
                    'name': plan_name,
                    'tasks_total': total or 1,
                    'tasks_done_start': done,
                }

    # Determine report title — use plan name if meaningful, else git-based
    if plan_progress and plan_progress['name'] and \
       plan_progress['name'] not in ('iteration', 'plan', 'untitled'):
        report_title = plan_progress['name'].replace('-', ' ').replace('_', ' ')
    elif current_commit:
        # Use recent commit message as title
        commit_msg = current_commit.split(' ', 1)[-1] if ' ' in current_commit else current_commit
        report_title = commit_msg[:80]
    else:
        report_title = f'迭代 {now.strftime("%Y-%m-%d %H:%M")}'

    # Build markdown report
    lines = []
    lines.append(f'# {report_title}')
    lines.append('')
    lines.append(f'**生成时间**: {now.strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append(f'**项目**: {os.path.basename(project_dir)}')
    lines.append(f'**分支**: {current_branch or "N/A"}')
    if current_commit:
        lines.append(f'**最新提交**: {current_commit}')
    lines.append('')

    # Plan context summary (if we have plan content)
    if plan_content.strip():
        # Extract first meaningful paragraph from plan as context
        plan_lines = plan_content.strip().split('\n')
        context_lines = []
        in_meta = True
        for pl in plan_lines:
            ps = pl.strip()
            if not ps:
                continue
            if ps.startswith('# '):
                in_meta = False
                continue
            if in_meta and (ps.startswith('##') or ps.startswith('**') or ps.startswith('---')):
                continue
            if ps.startswith('##'):
                break
            if len(ps) > 20:
                context_lines.append(ps)
                if len(context_lines) >= 3:
                    break
        if context_lines:
            lines.append('## 上下文摘要')
            lines.append('')
            for cl in context_lines:
                lines.append(f'> {cl[:200]}')
                lines.append('>')
            lines.append('')

    # Section 1: Goal Achievement
    lines.append('## 一、目标达成情况')
    lines.append('')
    if plan_progress:
        lines.append(f'- **方案**: {plan_progress["name"]}')
        lines.append(f'- **迭代开始时任务进度**: {plan_progress["tasks_done_start"]}/{plan_progress["tasks_total"]}')
    else:
        lines.append('- 本次迭代未关联到特定实施方案')
    lines.append('')

    # Section 2: Changes Summary
    lines.append('## 二、变更摘要')
    lines.append('')
    if all_changed:
        lines.append(f'本次迭代共修改 **{len(all_changed)}** 个文件：')
        lines.append('')

        cat_labels = {
            'backend': '🔧 后端', 'frontend': '🎨 前端', 'test': '🧪 测试',
            'config': '⚙️ 配置', 'docs': '📝 文档', 'scripts': '📜 脚本',
            'other': '📦 其他'
        }
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            lines.append(f'- {cat_labels.get(cat, cat)}: {count} 文件')

        lines.append('')
        lines.append('### 修改文件列表')
        lines.append('')
        for f in all_changed[:30]:
            lines.append(f'- `{f}`')
        if len(all_changed) > 30:
            lines.append(f'- ... 及其他 {len(all_changed) - 30} 个文件')
    else:
        lines.append('无文件变更（可能为调研/设计阶段）。')

    lines.append('')

    if diff_stat:
        lines.append('### 代码统计')
        lines.append('```')
        lines.append(diff_stat[:500])
        lines.append('```')
        lines.append('')

    # Section 3.5: Test Results (only if code changed)
    test_results = None
    if _has_code_changes(all_changed):
        passed, failed, errors, skipped, test_output = _run_tests(project_dir)
        test_results = {
            'passed': passed, 'failed': failed, 'errors': errors, 'skipped': skipped
        }
        lines.append('## 三、测试结果')
        lines.append('')
        total = passed + failed + errors
        if total > 0:
            status_icon = '✅' if failed == 0 and errors == 0 else '❌'
            lines.append(f'{status_icon} **{passed}** 通过, **{failed}** 失败, **{errors}** 错误, **{skipped}** 跳过 (共 {total})')
        else:
            lines.append('⚠️ 未能获取测试结果（可能测试套件不存在或运行超时）')
        lines.append('')
        # Show failures inline
        if failed > 0 or errors > 0:
            lines.append('### 失败详情')
            lines.append('```')
            in_failure = False
            failure_lines = 0
            for line in test_output:
                if 'FAILED' in line or 'ERRORS' in line or 'assert' in line or 'Error' in line:
                    in_failure = True
                if in_failure:
                    lines.append(line[:200])
                    failure_lines += 1
                    if failure_lines > 40:
                        lines.append('... (truncated)')
                        break
            lines.append('```')
        lines.append('')

    # Section 4: Analysis
    lines.append('## 四、分析评估')
    lines.append('')
    if plan_progress and all_changed:
        lines.append(f'- **完成度评估**: 方案涉及 {plan_progress["tasks_total"]} 个任务，有实质性代码变更')
    elif plan_progress and not all_changed:
        lines.append('- **注意**: 本次迭代未检测到文件变更，可能为纯调研/设计阶段')
    else:
        lines.append('- 无活跃方案或未检测到代码变更')

    if categories:
        focus_areas = sorted(categories.items(), key=lambda x: -x[1])
        primary = focus_areas[0][0]
        labels = {
            'backend': '后端逻辑', 'frontend': '前端界面', 'test': '测试代码',
            'config': '配置管理', 'docs': '文档', 'scripts': '脚本工具'
        }
        lines.append(f'- **主要工作方向**: {labels.get(primary, primary)}')

    lines.append('')

    # Section 5: Next Steps
    lines.append('## 五、下一阶段建议')
    lines.append('')
    if plan_progress:
        remaining = plan_progress['tasks_total'] - plan_progress['tasks_done_start']
        if remaining > 0:
            lines.append(f'方案 **{plan_progress["name"]}** 还有约 {remaining} 个任务待完成：')
            lines.append('')
            lines.append('1. 检查 `CLAUDE.md` 和计划文件确认剩余任务清单')
            lines.append('2. 按优先级顺序完成未完成任务')
            lines.append('3. 完成后运行测试验证功能正确性')
        else:
            lines.append('方案任务已全部覆盖。建议：')
            lines.append('')
            lines.append('1. 运行完整测试套件验证所有功能')
            lines.append('2. 在浏览器中手动验证 UI 变更')
            lines.append('3. 更新相关文档')
    else:
        lines.append('1. 明确下一阶段目标和任务清单')
        lines.append('2. 创建或更新实施方案计划')
        lines.append('3. 设置迭代追踪基准点')

    if staged_files:
        lines.append('')
        lines.append(f'⚠️ **注意**: 有 {len(staged_files)} 个文件已暂存但未提交')

    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append(f'*报告由 iteration-report.sh 自动生成于 {now.strftime("%Y-%m-%d %H:%M:%S")}*')

    report_md = '\n'.join(lines)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_md)

    # Update INDEX.md
    _update_index(iteration_dir, report_filename, report_title)

    # Clean up start record (consumed by this report)
    if start_data:
        for old in glob.glob(os.path.join(iteration_dir, '*-start.json')):
            try:
                os.remove(old)
            except OSError:
                pass

    # Build summary
    parts = [
        f'📊 迭代报告已生成',
        f'  项目: {os.path.basename(project_dir)}',
        f'  分支: {current_branch or "N/A"}',
    ]
    if all_changed:
        parts.append(f'  变更: {len(all_changed)} 文件')
        cat_parts = []
        cat_short = {'backend': '后端', 'frontend': '前端', 'test': '测试',
                     'config': '配置', 'docs': '文档', 'scripts': '脚本'}
        for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:3]:
            cat_parts.append(f'{cat_short.get(cat, cat)}:{count}')
        parts.append(f'  分布: {" ".join(cat_parts)}')
    if plan_progress:
        parts.append(f'  方案: {plan_progress["name"][:50]}')
    if test_results:
        passed, failed, errors = test_results['passed'], test_results['failed'], test_results['errors']
        if failed > 0 or errors > 0:
            parts.append(f'  ❌ 测试: {passed}通过 {failed}失败 {errors}错误')
        else:
            parts.append(f'  ✅ 测试: {passed}通过')
    parts.append(f'  报告: {os.path.basename(report_file)}')

    summary = '\n'.join(parts)
    print(json.dumps({'reportFile': report_file, 'summary': summary}, ensure_ascii=False))


if __name__ == '__main__':
    main()
