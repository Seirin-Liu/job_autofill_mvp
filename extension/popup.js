const API = 'http://127.0.0.1:8765';

const statusText = document.getElementById('statusText');
const statusDot = document.getElementById('statusDot');
const scanBtn = document.getElementById('scanBtn');
const pickBtn = document.getElementById('pickBtn');
const resultBox = document.getElementById('resultBox');
const useAi = document.getElementById('useAi');
const profileForm = document.getElementById('profileForm');
const profileMsg = document.getElementById('profileMsg');
const modelInput = document.getElementById('modelInput');
const importSummary = document.getElementById('importSummary');
const hiddenProfileSummary = document.getElementById('hiddenProfileSummary');

for (const tab of document.querySelectorAll('.tab')) {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab).classList.add('active');
  });
}

async function api(path, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  const response = await fetch(`${API}${path}`, {
    headers: {'Content-Type': 'application/json', ...(options.headers || {})},
    ...(method === 'GET' ? {cache: 'no-store'} : {}),
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function setByPath(obj, path, value) {
  const tokens = [...path.matchAll(/([^.[\]]+)|\[(\d+)\]/g)].map(m => m[1] ?? Number(m[2]));
  let cur = obj;
  for (let i = 0; i < tokens.length - 1; i++) {
    const t = tokens[i];
    const next = tokens[i + 1];
    if (cur[t] == null) cur[t] = typeof next === 'number' ? [] : {};
    if (Array.isArray(cur) && typeof t === 'number' && cur[t] == null) {
      cur[t] = typeof next === 'number' ? [] : {};
    }
    cur = cur[t];
  }
  cur[tokens[tokens.length - 1]] = value;
}

function getByPath(obj, path) {
  const tokens = [...path.matchAll(/([^.[\]]+)|\[(\d+)\]/g)].map(m => m[1] ?? Number(m[2]));
  let cur = obj;
  for (const t of tokens) {
    if (cur == null) return '';
    cur = cur[t];
  }
  return cur ?? '';
}

function profileCounts(profile) {
  return {
    education: Array.isArray(profile.education) ? profile.education.length : 0,
    internships: Array.isArray(profile.internships) ? profile.internships.length : 0,
    projects: Array.isArray(profile.projects) ? profile.projects.length : 0,
    activities: Array.isArray(profile.student_activities) ? profile.student_activities.length : 0,
    campus: profile.campus_experience?.description ? 1 : 0,
    awards: Array.isArray(profile.awards) ? profile.awards.length : 0,
    family: Array.isArray(profile.family?.members) ? profile.family.members.length : 0,
  };
}

async function refreshStatus() {
  try {
    const s = await api('/api/status');
    statusDot.className = 'dot ok';
    const who = s.profile_name ? ` · 档案 ${s.profile_name}` : '';
    statusText.textContent = `本地服务已连接${who} · AI ${s.deepseek_configured ? '已配置' : '未配置'}`;
    modelInput.value = s.model || '';
    scanBtn.disabled = false;
    pickBtn.disabled = false;
  } catch (e) {
    statusDot.className = 'dot bad';
    statusText.textContent = '无法连接 127.0.0.1:8765';
    scanBtn.disabled = true;
    pickBtn.disabled = true;
  }
}

async function loadProfile() {
  try {
    const data = await api('/api/profile');
    const profile = data.profile || {};
    for (const input of profileForm.querySelectorAll('[name]')) {
      let value = getByPath(profile, input.name);
      if (Array.isArray(value)) value = value.join(', ');
      input.value = value ?? '';
    }
    const counts = profileCounts(profile);
    const name = getByPath(profile, 'basic.name_cn') || '未命名档案';
    importSummary.innerHTML = `<strong>${name}</strong><br>已导入 ${counts.education} 条教育经历、${counts.internships} 条实习、${counts.projects} 条项目/科研经历、${counts.campus} 条校园经历、${counts.awards} 条荣誉。`;
    hiddenProfileSummary.textContent = `另有 ${counts.activities} 条社团经历、${counts.awards} 条个人荣誉、${counts.family} 位家庭成员，以及文档中的两张照片路径，均已保存在本地档案。`;
  } catch (e) {
    importSummary.textContent = `读取档案失败：${e.message}`;
  }
}

profileForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  profileMsg.textContent = '保存中…';
  try {
    const current = await api('/api/profile');
    const profile = current.profile || {};
    for (const input of profileForm.querySelectorAll('[name]')) {
      let value = input.value.trim();
      if (input.name === 'job_preferences.cities' || input.name === 'job_preferences.job_types') {
        value = value ? value.split(/[,，]/).map(x => x.trim()).filter(Boolean) : [];
      } else if (input.name === 'personality.words') {
        value = value ? value.split(/[,，、\s]+/).map(x => x.trim()).filter(Boolean) : [];
      }
      setByPath(profile, input.name, value);
    }
    // Keep the source-derived convenience text in sync for common long-form fields.
    profile.summaries = profile.summaries || {};
    profile.summaries.personality_text = (profile.personality?.words || []).join('、');
    await api('/api/profile', {method: 'PUT', body: JSON.stringify({profile})});
    profileMsg.textContent = '已保存到本机 SQLite。';
    await loadProfile();
    await refreshStatus();
  } catch (e) {
    profileMsg.textContent = `保存失败：${e.message}`;
  }
});

document.getElementById('saveModelBtn').addEventListener('click', async () => {
  try {
    await api('/api/model', {method: 'PUT', body: JSON.stringify({model: modelInput.value.trim()})});
    statusText.textContent = '模型设置已保存';
  } catch (e) {
    statusText.textContent = `保存失败：${e.message}`;
  }
});

pickBtn.addEventListener('click', async () => {
  pickBtn.disabled = true;
  resultBox.classList.add('muted');
  resultBox.textContent = '正在读取本地档案…';
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id) throw new Error('无法获取当前标签页');
    const response = await chrome.tabs.sendMessage(tab.id, {type: 'JOB_AUTOFILL_OPEN_PICKER'});
    if (!response?.ok) throw new Error(response?.error || '页面脚本未响应。请刷新招聘页面后重试。');
    const stats = response.stats || {};
    resultBox.classList.remove('muted');
    resultBox.textContent = `已打开本地数据快捷填入：共 ${stats.total || 0} 条数据。先点网页目标字段，再点一条本地数据即可写入。`;
    setTimeout(() => window.close(), 180);
  } catch (e) {
    resultBox.textContent = `失败：${e.message}`;
  } finally {
    pickBtn.disabled = false;
  }
});

scanBtn.addEventListener('click', async () => {
  scanBtn.disabled = true;
  resultBox.classList.add('muted');
  resultBox.textContent = '正在扫描并匹配字段…';
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id) throw new Error('无法获取当前标签页');
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: 'JOB_AUTOFILL_SCAN_AND_FILL',
      useAi: useAi.checked,
    });
    if (!response?.ok) throw new Error(response?.error || '页面脚本未响应。请刷新招聘页面后重试。');
    const s = response.stats;
    const rep = s.repeatable || {};
    const repLines = [];
    const reasonText = {
      'incomplete-required': '有必填字段未成功写入',
      'validation-error': '网站校验未通过',
      'confirm-timeout': '提交后页面没有确认成功',
      'no-fields': '未识别到可填写字段',
      'no-confirm-button': '未找到确认/添加按钮',
      'editor-timeout': '未识别到新增表单',
      'blocked-by-internship-failure': '因实习填写失败而暂停，防止误填',
      'blocked-by-prior-repeatable-failure': '前一个逐条新增模块失败，已暂停以防误填',
    };
    const repeatLine = (label, item) => {
      if (!item?.detected && !item?.blocked) return null;
      let line = `${label}：新增 ${item.added}/${item.total} · 已存在 ${item.skipped} · 失败 ${item.failed}`;
      if (item.stopped) {
        const detail = item.details?.find(x => !['added', 'skipped'].includes(x.status));
        const why = reasonText[item.stop_reason] || item.stop_reason || '已停止';
        const identity = detail?.identity ? `（${detail.identity}）` : '';
        const messages = [...(detail?.problems || []), ...(detail?.errors || [])].filter(Boolean).slice(0, 2);
        line += `
  已停止${identity}：${why}${messages.length ? `；${messages.join('；')}` : ''}`;
      }
      return line;
    };
    const internshipLine = repeatLine('实习经历', rep.internships);
    if (internshipLine) repLines.push(internshipLine);
    const projectLine = repeatLine('项目/科研经历', rep.projects);
    if (projectLine) repLines.push(projectLine);
    const awardLine = repeatLine('获奖经历', rep.awards);
    if (awardLine) repLines.push(awardLine);
    const familyLine = repeatLine('家庭关系', rep.family);
    if (familyLine) repLines.push(familyLine);
    resultBox.classList.remove('muted');
    resultBox.textContent = `普通字段：检测 ${s.total} · 匹配 ${s.matched} · 填写 ${s.filled}\n规则 ${s.rule} · 历史 ${s.history} · AI ${s.ai}${repLines.length ? `\n${repLines.join('\n')}` : ''}`;
  } catch (e) {
    resultBox.textContent = `失败：${e.message}`;
  } finally {
    scanBtn.disabled = false;
  }
});

refreshStatus();
loadProfile();
