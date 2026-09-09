(() => {
  const API = 'http://127.0.0.1:8765';
  let registry = new Map();

  const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, 500);
  const norm = (s) => clean(s).toLowerCase().replace(/[\s:：*＊()（）\[\]【】_\-—/、，,.。]+/g, '');
  const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  const REPEATABLE_CONFIG = {
    internships: {
      sectionAliases: [
        '实习（工作）及社会经历', '实习(工作)及社会经历', '实习工作及社会经历',
        '实习及社会经历', '实习经历', '工作及社会经历', '工作经历', '社会实践经历'
      ],
      identityKey: 'company',
      defaults: {},
      requiredKeys: ['work_type', 'company', 'role', 'start_date', 'end_date', 'description'],
      signatureKeys: ['company', 'role', 'start_date', 'end_date'],
      fields: {
        work_type: ['工作类型', '经历类型', '实习类型', '工作性质'],
        company: ['工作单位', '单位名称', '公司名称', '实习单位', '实践单位'],
        role: ['岗位', '职位', '职务', '工作岗位', '实习岗位'],
        city: ['所在城市', '工作城市', '城市'],
        start_date: ['入职时间', '开始时间', '起始时间', '开始日期', '实习开始时间'],
        end_date: ['离职时间', '结束时间', '终止时间', '结束日期', '实习结束时间'],
        description: ['主要工作职责和业绩', '工作职责和业绩', '主要工作职责', '工作职责', '工作内容', '实践内容', '主要职责', '工作业绩'],
        salary: ['职位月薪税前', '职位月薪', '月薪税前', '月薪', '薪资', '税前月薪'],
        contact_name: ['单位联系人', '联系人', '单位联系人员'],
        contact_phone: ['单位联系电话', '联系人电话', '联系电话']
      },
      editorHints: ['工作单位', '岗位', '入职时间', '离职时间', '主要工作职责'],
    },
    projects: {
      sectionAliases: ['项目经历', '项目经验', '科研经历', '项目与科研经历', '科研项目', '主要项目'],
      identityKey: 'name',
      defaults: {},
      requiredKeys: ['name', 'start_date', 'end_date', 'description'],
      signatureKeys: ['name', 'start_date', 'end_date'],
      fields: {
        name: ['项目名称', '课题名称', '科研项目名称', '名称'],
        type: ['项目类型', '经历类型', '项目类别', '类型'],
        role: ['项目角色', '担任角色', '职责', '角色'],
        start_date: ['项目开始时间', '开始时间', '起始时间', '开始日期'],
        end_date: ['项目结束时间', '结束时间', '终止时间', '结束日期'],
        tech_stack: ['技术栈', '项目技术栈', '使用技术', '技术框架', '开发技术'],
        description: ['项目内容', '项目描述', '项目简介', '主要内容', '项目职责'],
        result: ['项目成果', '科研成果', '论文成果', '项目业绩', '成果']
      },
      editorHints: ['项目名称', '开始时间', '结束时间', '项目内容'],
    },
    awards: {
      sectionAliases: ['获奖经历', '获奖情况', '奖励经历', '荣誉奖励', '奖项经历', '个人荣誉'],
      identityKey: 'name',
      defaults: {},
      requiredKeys: ['date', 'name'],
      signatureKeys: ['name', 'date'],
      fields: {
        date: ['获奖时间', '奖项时间', '时间', '日期'],
        name: ['奖项名称', '获奖名称', '荣誉名称', '奖励名称'],
        level: ['奖项级别', '获奖级别', '级别'],
        type: ['奖项类型', '荣誉类型', '类型'],
        reference: ['出版书号期刊名称专利号', '期刊名称', '专利号', '参考信息'],
        details: ['详细说明', '获奖说明', '奖项说明', '备注']
      },
      editorHints: ['奖项名称', '获奖时间', '时间'],
    },
    family: {
      sectionAliases: ['家庭关系', '家庭成员', '家庭成员信息', '亲属信息', '家庭信息'],
      identityKey: 'name',
      defaults: {},
      requiredKeys: ['relation', 'name', 'age', 'employer', 'department', 'position', 'phone', 'political_status', 'is_china_post_employee'],
      signatureKeys: ['relation', 'name', 'phone'],
      fields: {
        relation: ['与本人关系', '与申请人关系', '亲属关系', '关系'],
        name: ['亲属姓名', '家庭成员姓名', '成员姓名', '姓名'],
        age: ['年龄'],
        employer: ['工作单位', '所在单位', '单位名称', '工作机构'],
        department: ['工作部门', '所在部门', '部门'],
        position: ['职务', '职位', '岗位'],
        phone: ['联系电话', '手机号码', '手机号', '电话'],
        political_status: ['政治面貌', '政治身份'],
        is_china_post_employee: ['是否为中国邮政系统职工', '是否中国邮政系统职工', '中国邮政系统职工']
      },
      editorHints: ['与本人关系', '亲属姓名', '工作单位', '联系电话'],
    },
  };

  const VALUE_ALIASES = {
    '实习': ['实习', '实习经历', '实习工作', '社会实践', '实践'],
    '奖项': ['奖项', '获奖', '奖励', '荣誉'],
    '省区级': ['省区级', '省级', '省/自治区/直辖市级'],
    '国家级': ['国家级', '全国级'],
    '院校级': ['院校级', '校级', '学校级'],
    '父亲': ['父亲', '父', '爸爸'],
    '母亲': ['母亲', '母', '妈妈'],
    '群众': ['群众', '普通群众'],
  };

  function isVisible(el) {
    if (!el || !el.isConnected) return false;
    if ('disabled' in el && el.disabled) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function dispatch(el) {
    for (const type of ['input', 'change']) {
      el.dispatchEvent(new Event(type, {bubbles: true}));
    }
  }

  function setNativeValue(el, value, options = {}) {
    const {blur = true} = options;
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
    try { el.focus(); } catch (_) {}
    if (descriptor?.set) descriptor.set.call(el, String(value ?? ''));
    else el.value = String(value ?? '');
    dispatch(el);
    if (blur) { try { el.blur(); } catch (_) {} }
  }

  function appendNativeValue(el, value, options = {}) {
    const {blur = true} = options;
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
    const current = String(el.value ?? '');
    const addition = String(value ?? '');
    const combined = current + addition;
    try { el.focus(); } catch (_) {}
    if (descriptor?.set) descriptor.set.call(el, combined);
    else el.value = combined;
    try {
      const end = combined.length;
      el.setSelectionRange?.(end, end);
    } catch (_) {}
    dispatch(el);
    if (blur) { try { el.blur(); } catch (_) {} }
  }

  function labelFor(el) {
    const parts = [];
    if (el.labels?.length) parts.push(...[...el.labels].map(l => l.innerText));
    const aria = el.getAttribute?.('aria-label');
    if (aria) parts.push(aria);
    const labelledBy = el.getAttribute?.('aria-labelledby');
    if (labelledBy) {
      for (const id of labelledBy.split(/\s+/)) {
        const node = document.getElementById(id);
        if (node) parts.push(node.innerText || node.textContent);
      }
    }
    if (el.placeholder) parts.push(el.placeholder);
    if (el.name) parts.push(el.name);

    const parent = el.closest?.(
      'label, .form-item, .ant-form-item, .el-form-item, .arco-form-item, [class*="form-item"], [class*="formItem"], [class*="field-item"], [class*="fieldItem"]'
    );
    if (parent) {
      const text = clean(parent.innerText || parent.textContent);
      if (text && text.length <= 240) parts.push(text);
    }

    const prev = el.previousElementSibling;
    if (prev) {
      const text = clean(prev.innerText || prev.textContent);
      if (text.length <= 120) parts.push(text);
    }
    return clean(parts.filter(Boolean).join(' | '));
  }

  function nearbySectionHeading(el) {
    const selectors = 'h1, h2, h3, h4, h5, h6, legend, [class*="section-title"], [class*="sectionTitle"], [class*="module-title"], [class*="moduleTitle"]';
    const targetTop = el.getBoundingClientRect().top + window.scrollY;
    let best = '';
    let bestTop = -Infinity;
    for (const node of document.querySelectorAll(selectors)) {
      if (!isVisible(node)) continue;
      const text = clean(node.innerText || node.textContent);
      if (!text || text.length > 80) continue;
      const top = node.getBoundingClientRect().top + window.scrollY;
      if (top <= targetTop && top > bestTop && targetTop - top < 1800) {
        best = text;
        bestTop = top;
      }
    }
    return best;
  }

  function contextFor(el) {
    const container = el.closest?.(
      'fieldset, .form-item, .ant-form-item, .el-form-item, .arco-form-item, [class*="form-item"], [class*="formItem"], [class*="field-item"], [class*="fieldItem"], div'
    );
    const local = container ? clean(container.innerText || container.textContent) : '';
    const heading = nearbySectionHeading(el);
    return clean([heading, local].filter(Boolean).join(' | ')).slice(0, 220);
  }

  function fingerprint(meta) {
    return [meta.type, norm(meta.label), norm(meta.placeholder), norm(meta.name), meta.options.map(norm).join('|')].join('::').slice(0, 1000);
  }

  function optionText(el) {
    const label = el.labels?.[0]?.innerText;
    if (label) return clean(label);
    const parentLabel = el.closest?.('label');
    if (parentLabel) return clean(parentLabel.innerText);
    return clean(el.value);
  }

  function scanFields(root = document) {
    registry = new Map();
    const fields = [];
    const elements = [...root.querySelectorAll('input, textarea, select')].filter(isVisible);
    const processedRadioNames = new Set();

    for (const el of elements) {
      const inputType = (el.getAttribute('type') || el.tagName.toLowerCase()).toLowerCase();
      if (['hidden', 'submit', 'button', 'reset', 'image', 'file', 'password'].includes(inputType)) continue;

      if ((inputType === 'radio' || inputType === 'checkbox') && el.name) {
        const groupKey = `${inputType}:${el.name}`;
        if (processedRadioNames.has(groupKey)) continue;
        processedRadioNames.add(groupKey);
        const scope = root === document ? document : root;
        const groupEls = [...scope.querySelectorAll(`input[type="${inputType}"]`)].filter(x => x.name === el.name && isVisible(x));
        const id = `ja_${fields.length}_${Math.random().toString(36).slice(2, 7)}`;
        const options = groupEls.map(optionText).filter(Boolean);
        const meta = {
          id,
          label: labelFor(el),
          placeholder: '',
          name: el.name || '',
          type: inputType,
          options,
          context: contextFor(el),
        };
        meta.fingerprint = fingerprint(meta);
        registry.set(id, {kind: inputType, elements: groupEls, meta});
        fields.push(meta);
        continue;
      }

      const id = `ja_${fields.length}_${Math.random().toString(36).slice(2, 7)}`;
      const options = el.tagName === 'SELECT'
        ? [...el.options].map(o => clean(o.textContent || o.value)).filter(x => x && !/请选择|please select/i.test(x))
        : [];
      const meta = {
        id,
        label: labelFor(el),
        placeholder: el.placeholder || '',
        name: el.name || '',
        type: el.tagName === 'SELECT' ? 'select' : inputType,
        options,
        context: contextFor(el),
      };
      meta.fingerprint = fingerprint(meta);
      registry.set(id, {kind: meta.type, element: el, meta});
      fields.push(meta);
    }
    return fields;
  }

  function chooseSelect(el, value) {
    const candidates = candidateValues(value).map(norm);
    let best = null;
    for (const option of [...el.options]) {
      const ot = clean(option.textContent || option.value);
      if (!ot) continue;
      const nTexts = [norm(ot), norm(option.value)];
      if (nTexts.some(x => candidates.includes(x))) { best = option; break; }
      if (!best && nTexts.some(x => candidates.some(v => x.includes(v) || v.includes(x)))) best = option;
    }
    if (!best) return false;
    el.value = best.value;
    dispatch(el);
    try { el.blur(); } catch (_) {}
    return true;
  }

  function chooseGroup(elements, value) {
    const values = candidateValues(value).map(norm);
    let best = null;
    for (const el of elements) {
      const candidates = [optionText(el), el.value].map(norm);
      if (candidates.some(x => values.includes(x))) { best = el; break; }
      if (!best && candidates.some(x => x && values.some(v => x.includes(v) || v.includes(x)))) best = el;
    }
    if (!best) return false;
    best.click();
    dispatch(best);
    return true;
  }

  function fillOne(match) {
    const item = registry.get(match.id);
    if (!item || !match.profile_key || match.fill_value == null || match.fill_value === '') return false;
    try {
      if (item.kind === 'radio' || item.kind === 'checkbox') return chooseGroup(item.elements, match.fill_value);
      if (item.kind === 'select') return chooseSelect(item.element, match.fill_value);
      setNativeValue(item.element, match.fill_value);
      return true;
    } catch (_) {
      return false;
    }
  }

  function candidateValues(value) {
    const raw = clean(value);
    const aliases = VALUE_ALIASES[raw] || [];
    return [raw, ...aliases].filter(Boolean);
  }

  function clickableFromNode(node) {
    if (!node) return null;
    if (node.matches?.('button, a, [role="button"]')) return node;
    let cur = node;
    for (let i = 0; i < 4 && cur; i += 1, cur = cur.parentElement) {
      if (cur.matches?.('button, a, [role="button"]')) return cur;
      const cls = String(cur.className || '').toLowerCase();
      const style = window.getComputedStyle(cur);
      if ((cls.includes('button') || cls.includes('btn') || cls.includes('add')) && style.cursor === 'pointer') return cur;
      if (cur.onclick) return cur;
    }
    return null;
  }

  function clickableText(el) {
    return clean(el?.innerText || el?.textContent || el?.getAttribute?.('aria-label') || el?.title || '');
  }

  function findClickables(root, acceptedTexts) {
    const accepted = acceptedTexts.map(norm);
    const results = new Set();
    const direct = root.querySelectorAll?.('button, a, [role="button"], input[type="button"], input[type="submit"]') || [];
    for (const el of direct) {
      if (!isVisible(el)) continue;
      const t = norm(clickableText(el) || el.value);
      if (accepted.some(a => t === a || t.includes(a))) results.add(el);
    }
    const textNodes = root.querySelectorAll?.('span, div, p') || [];
    for (const node of textNodes) {
      if (!isVisible(node)) continue;
      const txt = clean(node.innerText || node.textContent);
      if (!txt || txt.length > 12 || !accepted.some(a => norm(txt) === a)) continue;
      const clickable = clickableFromNode(node);
      if (clickable && isVisible(clickable)) results.add(clickable);
    }
    return [...results];
  }

  function findSection(kind) {
    const cfg = REPEATABLE_CONFIG[kind];
    if (!cfg) return null;
    const aliases = cfg.sectionAliases.map(norm);
    const nodes = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,legend,div,span,p')]
      .filter(isVisible)
      .filter(el => {
        const text = clean(el.innerText || el.textContent);
        if (!text || text.length > 80) return false;
        const n = norm(text);
        return aliases.some(a => n === a || n.startsWith(a) || (a.length >= 4 && n.includes(a)));
      });

    for (const heading of nodes) {
      let cur = heading;
      let fallback = null;
      for (let depth = 0; depth < 8 && cur && cur !== document.body; depth += 1, cur = cur.parentElement) {
        const adds = findClickables(cur, ['添加']);
        if (adds.length) {
          fallback = {section: cur, heading};
          const controls = cur.querySelectorAll('input, textarea, select').length;
          const textLen = clean(cur.innerText || cur.textContent).length;
          if (depth >= 1 && (controls > 0 || textLen < 2500)) return fallback;
        }
      }
      if (fallback) return fallback;
    }
    return null;
  }

  function pickSectionAddButton(sectionInfo) {
    if (!sectionInfo) return null;
    const {section, heading} = sectionInfo;
    const buttons = findClickables(section, ['添加']);
    if (!buttons.length) return null;
    const hr = heading.getBoundingClientRect();
    const scored = buttons.map(button => {
      const r = button.getBoundingClientRect();
      let score = Math.abs(r.top - hr.top);
      if (r.top >= hr.top - 30 && r.top <= hr.bottom + 70) score -= 1000;
      if (button.matches('button, [role="button"]')) score -= 20;
      return {button, score};
    });
    scored.sort((a, b) => a.score - b.score);
    return scored[0].button;
  }

  function visibleControls(root) {
    return [...root.querySelectorAll('input, textarea, select, [role="combobox"]')]
      .filter(isVisible)
      .filter((el, idx, arr) => {
        if (el.matches('[role="combobox"]') && el.tagName !== 'INPUT' && el.querySelector('input')) return false;
        return arr.indexOf(el) === idx;
      });
  }

  function commonAncestor(nodes) {
    if (!nodes.length) return null;
    let cur = nodes[0];
    while (cur && cur !== document.body) {
      if (nodes.every(n => cur.contains(n))) return cur;
      cur = cur.parentElement;
    }
    return document.body;
  }

  function editorKeySet(el, kind) {
    const keys = new Set();
    for (const control of visibleControls(el)) {
      const key = fieldKeyForLabel(kind, labelFor(control));
      if (key) keys.add(key);
    }
    return keys;
  }

  function editorLooksRight(el, kind) {
    if (!el || !isVisible(el)) return false;
    const keys = editorKeySet(el, kind);
    if (kind === 'internships') {
      return keys.has('company') && (keys.has('role') || keys.has('start_date')) && keys.size >= 3;
    }
    if (kind === 'awards') {
      // “时间” alone is intentionally insufficient: an open internship editor also contains dates.
      return keys.has('name') && keys.has('date');
    }
    if (kind === 'family') {
      return keys.has('relation') && keys.has('name') && (keys.has('phone') || keys.has('employer')) && keys.size >= 4;
    }
    return false;
  }

  function detectEditor(sectionInfo, beforeControls, kind) {
    const dialogs = [...document.querySelectorAll('[role="dialog"], .ant-modal, .el-dialog, .arco-modal, [class*="modal"], [class*="drawer"]')]
      .filter(isVisible)
      .filter(el => editorLooksRight(el, kind));
    if (dialogs.length) return dialogs.sort((a, b) => visibleControls(b).length - visibleControls(a).length)[0];

    const sectionNow = findSection(kind)?.section || sectionInfo.section;
    const current = visibleControls(sectionNow);
    const added = current.filter(el => !beforeControls.has(el));
    if (added.length) {
      let root = commonAncestor(added);
      for (let i = 0; i < 6 && root && root !== sectionNow.parentElement; i += 1, root = root.parentElement) {
        if (editorLooksRight(root, kind) && findClickables(root, ['添加', '确定', '保存', '确认']).length) return root;
      }
    }

    const candidates = [...sectionNow.querySelectorAll('form, [class*="form"], [class*="edit"], [class*="editor"], [class*="content"], div')]
      .filter(isVisible)
      .filter(el => editorLooksRight(el, kind))
      .filter(el => findClickables(el, ['添加', '确定', '保存', '确认']).length);
    candidates.sort((a, b) => visibleControls(a).length - visibleControls(b).length);
    return candidates[0] || null;
  }

  async function waitFor(fn, timeout = 2500, interval = 80) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const result = fn();
      if (result) return result;
      await sleep(interval);
    }
    return null;
  }

  function fieldKeyForLabel(kind, label) {
    const cfg = REPEATABLE_CONFIG[kind];
    const n = norm(label);
    if (!n) return null;
    let best = null;
    for (const [key, aliases] of Object.entries(cfg.fields)) {
      for (const alias of aliases) {
        const a = norm(alias);
        let score = 0;
        if (n === a) score = 1000 + a.length;
        else if (n.startsWith(a) || n.includes(a)) score = 800 + a.length;
        else if (a.includes(n) && n.length >= 2) score = 500 + n.length;
        if (score && (!best || score > best.score)) best = {key, score};
      }
    }
    return best?.key || null;
  }

  function normalizeRecord(kind, record) {
    const cfg = REPEATABLE_CONFIG[kind];
    return {...cfg.defaults, ...(record || {})};
  }

  function formatForControl(el, value) {
    const raw = clean(value);
    if (!raw) return raw;
    const type = (el.getAttribute?.('type') || '').toLowerCase();
    const placeholder = clean(el.getAttribute?.('placeholder') || '');
    if (type === 'month') return raw.slice(0, 7);
    if (/yyyy[\s\-/]?mm(?![\s\-/]?dd)/i.test(placeholder)) return raw.slice(0, 7);
    return raw;
  }

  function customSelectRoot(el) {
    if (!el) return null;
    return el.closest?.('.ant-select, .el-select, .arco-select, [class*="select"]') || (el.getAttribute?.('role') === 'combobox' ? el : null);
  }

  function visibleOptionNodes() {
    const selectors = [
      '[role="option"]', '.ant-select-item-option', '.el-select-dropdown__item', '.arco-select-option',
      '[class*="select-option"]', '[class*="dropdown-item"]'
    ];
    const nodes = new Set();
    for (const selector of selectors) {
      for (const el of document.querySelectorAll(selector)) {
        if (isVisible(el)) nodes.add(el);
      }
    }
    return [...nodes];
  }

  function controlMeta(el, id) {
    const options = el.tagName === 'SELECT'
      ? [...el.options].map(o => clean(o.textContent || o.value)).filter(x => x && !/请选择|please select/i.test(x))
      : [];
    return {
      id,
      label: labelFor(el),
      placeholder: el.getAttribute?.('placeholder') || '',
      name: el.getAttribute?.('name') || '',
      type: el.tagName === 'SELECT' ? 'select' : ((el.getAttribute?.('type') || el.getAttribute?.('role') || el.tagName).toLowerCase()),
      options,
      context: contextFor(el),
      fingerprint: '',
    };
  }

  async function postJson(path, payload) {
    const response = await fetch(`${API}${path}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`本地服务返回 ${response.status}`);
    return response.json();
  }

  function dateLike(el, label = '') {
    const type = (el.getAttribute?.('type') || '').toLowerCase();
    const cls = String(el.className || '') + ' ' + String(el.parentElement?.className || '');
    const ph = clean(el.getAttribute?.('placeholder') || '');
    return ['date', 'month'].includes(type) || /日期|时间/.test(label) || /date|picker/i.test(cls) || /yyyy|年|月|日/i.test(ph);
  }

  function sendKey(el, key) {
    const code = key === 'Enter' ? 13 : 0;
    for (const type of ['keydown', 'keypress', 'keyup']) {
      el.dispatchEvent(new KeyboardEvent(type, {key, code: key, keyCode: code, which: code, bubbles: true}));
    }
  }

  async function setDateControl(el, value, label = '') {
    const input = el.tagName === 'INPUT' ? el : el.querySelector?.('input');
    if (!input) return false;
    const formatted = formatForControl(input, value);
    if (!formatted) return false;
    try { input.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (_) {}
    try { input.click(); } catch (_) {}
    await sleep(80);

    const wasReadOnly = input.readOnly;
    try { if (wasReadOnly) input.readOnly = false; } catch (_) {}
    try {
      setNativeValue(input, formatted, {blur: false});
      sendKey(input, 'Enter');
      await sleep(100);
      dispatch(input);
      try { input.blur(); } catch (_) {}
      await sleep(120);
    } finally {
      try { if (wasReadOnly) input.readOnly = true; } catch (_) {}
    }
    const current = clean(input.value);
    return !!current && (current.includes(formatted) || norm(current) === norm(formatted));
  }

  function selectedCustomText(el) {
    const root = customSelectRoot(el) || el;
    const selected = root.querySelector?.(
      '.ant-select-selection-item, .el-select__selected-item, .el-select__tags-text, .arco-select-view-value, [class*="selection-item"], [class*="selected-value"]'
    );
    if (selected && isVisible(selected)) return clean(selected.innerText || selected.textContent);
    if (el.tagName === 'INPUT' && el.value) return clean(el.value);
    return '';
  }

  function readControlValue(el) {
    if (!el) return '';
    if (el.tagName === 'SELECT') return clean(el.options?.[el.selectedIndex]?.textContent || el.value);
    if (customSelectRoot(el) || el.getAttribute?.('role') === 'combobox') {
      const selected = selectedCustomText(el);
      if (selected) return selected;
    }
    if ('value' in el) return clean(el.value);
    const input = el.querySelector?.('input,textarea');
    return clean(input?.value || '');
  }

  async function chooseOptionViaApi(kind, label, recordKey, value, options, record, useAi) {
    if (!options.length) return null;
    try {
      const data = await postJson('/api/repeatable/choose-option', {
        kind,
        field_label: label,
        record_key: recordKey,
        value,
        options,
        record,
        use_ai: !!useAi,
      });
      return data.choice || null;
    } catch (_) {
      return null;
    }
  }

  async function chooseCustomSelect(el, value, context) {
    const {kind, label, recordKey, record, useAi} = context;
    const initialValues = [];
    if (value != null && value !== '') initialValues.push(value);
    if (kind === 'internships' && recordKey === 'work_type') {
      // Different ATSes interpret this as employment type or functional category.
      initialValues.push(record.work_type || '', '实习', record.role || '');
    }
    const values = initialValues.flatMap(candidateValues).filter(Boolean).map(norm);
    const root = customSelectRoot(el) || el;
    try { root.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (_) {}
    try { root.click(); } catch (_) { try { el.click(); } catch (_) {} }
    await sleep(140);

    let options = visibleOptionNodes();
    if (!options.length) {
      await sleep(220);
      options = visibleOptionNodes();
    }
    let best = null;
    for (const option of options) {
      const t = norm(clickableText(option));
      if (!t) continue;
      if (values.includes(t)) { best = option; break; }
      if (!best && values.some(v => v && (t.includes(v) || v.includes(t)))) best = option;
    }

    if (!best && options.length) {
      const optionTexts = options.map(clickableText).map(clean).filter(Boolean);
      const choice = await chooseOptionViaApi(kind, label, recordKey, value, optionTexts, record, useAi);
      if (choice) best = options.find(o => clean(clickableText(o)) === choice) || null;
    }

    if (!best) {
      try { sendKey(el, 'Escape'); } catch (_) {}
      return false;
    }
    try { best.scrollIntoView({block: 'nearest'}); } catch (_) {}
    best.click();
    await sleep(120);
    return !!readControlValue(el) || true;
  }

  async function setRepeatControl(el, value, context) {
    const label = context.label || labelFor(el);
    const formatted = value == null ? '' : formatForControl(el, value);

    if (dateLike(el, label) && formatted) {
      const ok = await setDateControl(el, formatted, label);
      if (ok) return true;
    }

    if (el.tagName === 'SELECT') {
      if (formatted && chooseSelect(el, formatted)) return true;
      const options = [...el.options].map(o => clean(o.textContent || o.value)).filter(Boolean);
      const choice = await chooseOptionViaApi(context.kind, label, context.recordKey, value, options, context.record, context.useAi);
      return choice ? chooseSelect(el, choice) : false;
    }

    const role = el.getAttribute?.('role');
    const selectRoot = customSelectRoot(el);
    if (role === 'combobox' || (selectRoot && /ant-select|el-select|arco-select|select/i.test(String(selectRoot.className || '')))) {
      const selected = await chooseCustomSelect(el, formatted, context);
      if (selected) return true;
      if (!(el.tagName === 'INPUT' && !el.readOnly && formatted)) return false;
    }

    if (!formatted) return false;
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      setNativeValue(el, formatted);
      return !!readControlValue(el);
    }
    const inner = el.querySelector?.('input, textarea');
    if (inner && isVisible(inner)) {
      setNativeValue(inner, formatted);
      return !!readControlValue(inner);
    }
    return false;
  }

  function isRequiredControl(el) {
    if (el.required || el.getAttribute?.('aria-required') === 'true') return true;
    const item = el.closest?.('.ant-form-item, .el-form-item, .arco-form-item, [class*="form-item"], [class*="formItem"], label');
    if (!item) return false;
    const cls = String(item.className || '').toLowerCase();
    if (/required|is-required/.test(cls)) return true;
    const label = item.querySelector?.('label, [class*="label"]');
    const labelCls = String(label?.className || '').toLowerCase();
    if (/required/.test(labelCls)) return true;
    const text = clean(label?.innerText || label?.textContent || '');
    return /^[*＊]/.test(text) || /[*＊]\s*[^*＊]+/.test(text.slice(0, 60));
  }

  function highlightProblem(el) {
    try {
      const target = customSelectRoot(el) || el;
      target.scrollIntoView({block: 'center', inline: 'nearest'});
      target.style.outline = '2px solid #e5484d';
      target.style.outlineOffset = '2px';
    } catch (_) {}
  }

  async function fillEditor(kind, editor, record, useAi) {
    const normalized = normalizeRecord(kind, record);
    const controls = visibleControls(editor).filter(el => {
      const type = (el.getAttribute?.('type') || '').toLowerCase();
      return !['hidden', 'button', 'submit', 'reset', 'file', 'password'].includes(type);
    });
    const entries = controls.map((el, i) => ({el, meta: controlMeta(el, `repeat_${kind}_${i}`)}));
    let plan = {assignments: []};
    try {
      plan = await postJson('/api/repeatable/plan', {
        kind,
        controls: entries.map(x => x.meta),
        record: normalized,
        use_ai: !!useAi,
      });
    } catch (_) {
      // Local JS mapping remains as an offline fallback if a future backend endpoint is unavailable.
      plan.assignments = entries.map(({meta}) => {
        const key = fieldKeyForLabel(kind, meta.label);
        return key ? {id: meta.id, record_key: key, value: normalized[key], fill_value: normalized[key], source: 'js-rule'} : null;
      }).filter(Boolean);
    }

    const assignments = new Map((plan.assignments || []).map(x => [x.id, x]));
    const byKey = new Map();
    let filled = 0;
    const details = [];

    for (const entry of entries) {
      let assignment = assignments.get(entry.meta.id);
      if (!assignment) {
        const key = fieldKeyForLabel(kind, entry.meta.label);
        if (key) assignment = {record_key: key, value: normalized[key], fill_value: normalized[key], source: 'js-rule'};
      }
      if (!assignment?.record_key) continue;
      const key = assignment.record_key;
      const value = assignment.fill_value ?? assignment.value ?? normalized[key] ?? null;
      const ok = await setRepeatControl(entry.el, value, {
        kind,
        label: entry.meta.label,
        recordKey: key,
        record: normalized,
        useAi,
      });
      byKey.set(key, entry.el);
      if (ok) {
        filled += 1;
        details.push(key);
      }
    }

    const problems = [];
    for (const entry of entries) {
      const key = fieldKeyForLabel(kind, entry.meta.label);
      const shouldCheck = isRequiredControl(entry.el) || (key && REPEATABLE_CONFIG[kind].requiredKeys.includes(key));
      if (!shouldCheck) continue;
      if (!readControlValue(entry.el)) {
        const label = clean(entry.meta.label.split('|')[0]) || key || '必填字段';
        problems.push({key: key || null, label, el: entry.el});
      }
    }
    if (problems.length) highlightProblem(problems[0].el);
    return {filled, keys: details, problems, ai: plan.stats?.ai || 0};
  }

  function findConfirmButton(editor) {
    const buttons = findClickables(editor, ['添加', '确定', '保存', '确认']);
    if (!buttons.length) return null;
    const controls = visibleControls(editor);
    const lastControlBottom = controls.reduce((m, el) => Math.max(m, el.getBoundingClientRect().bottom), 0);
    const scored = buttons.map(button => {
      const rect = button.getBoundingClientRect();
      const text = norm(clickableText(button));
      let score = 0;
      if (text === norm('添加')) score += 100;
      if (text === norm('确定') || text === norm('保存') || text === norm('确认')) score += 80;
      if (rect.top >= lastControlBottom - 10) score += 60;
      const cls = String(button.className || '').toLowerCase();
      if (/primary|main|confirm/.test(cls)) score += 30;
      score += rect.top / 10000;
      return {button, score};
    });
    scored.sort((a, b) => b.score - a.score);
    return scored[0].button;
  }

  function collectValidationErrors(scope = document) {
    const selectors = [
      '.ant-form-item-explain-error', '.ant-form-item-extra', '.el-form-item__error', '.arco-form-message',
      '[role="alert"]', '.ant-message-error', '.ant-notification-notice-error', '.el-message--error',
      '[class*="error-message"]', '[class*="form-error"]'
    ];
    const found = new Set();
    for (const selector of selectors) {
      for (const el of scope.querySelectorAll?.(selector) || []) {
        if (!isVisible(el)) continue;
        const text = clean(el.innerText || el.textContent);
        if (text) found.add(text);
      }
    }
    // Some ATSes render validation as plain red text without semantic classes.
    for (const el of scope.querySelectorAll?.('div,span,p') || []) {
      if (!isVisible(el)) continue;
      const text = clean(el.innerText || el.textContent);
      if (text.length > 80) continue;
      if (/^请(?:选择|填写|输入|完善)|请填写完整|不能为空|必填/.test(text)) found.add(text);
    }
    return [...found];
  }

  function newErrors(before, after) {
    const old = new Set(before);
    return after.filter(x => !old.has(x));
  }

  async function submitEditor(kind, editor, record) {
    const confirm = findConfirmButton(editor);
    if (!confirm) return {status: 'no-confirm-button', errors: []};
    const beforeErrors = collectValidationErrors(document);
    try { confirm.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (_) {}
    confirm.click();

    const cfg = REPEATABLE_CONFIG[kind];
    const identity = clean(record?.[cfg.identityKey]);
    let outcome = null;
    const completed = await waitFor(() => {
      const afterErrors = collectValidationErrors(document);
      const freshErrors = newErrors(beforeErrors, afterErrors);
      if (freshErrors.length) {
        outcome = {status: 'validation-error', errors: freshErrors};
        return true;
      }
      const latest = findSection(kind);
      if (identity && latest && recordAlreadyPresent(kind, latest.section, record)) {
        outcome = {status: 'added', errors: []};
        return true;
      }
      if (!editor.isConnected || !isVisible(editor)) {
        outcome = {status: 'added', errors: []};
        return true;
      }
      return false;
    }, 3200, 100);
    if (!completed) {
      const errors = newErrors(beforeErrors, collectValidationErrors(document));
      return {status: errors.length ? 'validation-error' : 'confirm-timeout', errors};
    }
    return outcome || {status: 'confirm-timeout', errors: []};
  }

  function recordAlreadyPresent(kind, section, record) {
    const cfg = REPEATABLE_CONFIG[kind];
    const identity = clean(record?.[cfg.identityKey]);
    if (!identity || !section) return false;
    const text = norm(clean(section.innerText || section.textContent));
    return text.includes(norm(identity));
  }

  async function addOneRepeatable(kind, record, useAi) {
    let sectionInfo = findSection(kind);
    if (!sectionInfo) return {status: 'no-section', filled: 0};
    if (recordAlreadyPresent(kind, sectionInfo.section, record)) return {status: 'skipped', filled: 0};

    const before = new Set(visibleControls(sectionInfo.section));
    const trigger = pickSectionAddButton(sectionInfo);
    if (!trigger) return {status: 'no-add-button', filled: 0};
    try { trigger.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (_) {}
    trigger.click();

    const editor = await waitFor(() => detectEditor(sectionInfo, before, kind), 3200, 100);
    if (!editor) return {status: 'editor-timeout', filled: 0};

    let fill = await fillEditor(kind, editor, record, useAi);
    if (fill.filled === 0) return {status: 'no-fields', filled: 0, keys: [], problems: []};
    if (fill.problems.length) {
      return {
        status: 'incomplete-required',
        filled: fill.filled,
        keys: fill.keys,
        problems: fill.problems.map(x => x.label),
        ai: fill.ai,
      };
    }

    let submit = await submitEditor(kind, editor, record);
    if (submit.status === 'validation-error' && useAi && editor.isConnected && isVisible(editor)) {
      // One bounded repair pass only. The validation text often makes date/select widgets easier
      // to identify after the first attempt. Never loop indefinitely.
      await sleep(180);
      fill = await fillEditor(kind, editor, record, true);
      if (!fill.problems.length) submit = await submitEditor(kind, editor, record);
    }

    await sleep(160);
    return {
      status: submit.status,
      filled: fill.filled,
      keys: fill.keys,
      problems: fill.problems?.map(x => x.label) || [],
      errors: submit.errors || [],
      ai: fill.ai || 0,
    };
  }

  async function fillRepeatableCollection(kind, records, useAi) {
    const result = {
      detected: false,
      total: Array.isArray(records) ? records.length : 0,
      attempted: 0,
      added: 0,
      skipped: 0,
      failed: 0,
      stopped: false,
      stop_reason: '',
      details: [],
    };
    if (!Array.isArray(records) || records.length === 0) return result;
    result.detected = !!findSection(kind);
    if (!result.detected) return result;

    for (let index = 0; index < records.length; index += 1) {
      const record = records[index];
      const r = await addOneRepeatable(kind, record, useAi);
      result.attempted += 1;
      result.details.push({index, identity: clean(record?.[REPEATABLE_CONFIG[kind].identityKey]), ...r});
      if (r.status === 'added') result.added += 1;
      else if (r.status === 'skipped') result.skipped += 1;
      else {
        result.failed += 1;
        result.stopped = true;
        result.stop_reason = r.status;
        // Critical safety rule: a failed editor is normally still open. Continuing would let
        // the next internship/award overwrite the same form (the runaway behavior seen before).
        break;
      }
      await sleep(220);
    }
    return result;
  }

  function blockedRepeatable(kind, records, reason) {
    return {
      detected: !!findSection(kind),
      total: Array.isArray(records) ? records.length : 0,
      attempted: 0,
      added: 0,
      skipped: 0,
      failed: 0,
      stopped: true,
      blocked: true,
      stop_reason: reason,
      details: [],
    };
  }

  let pickerHost = null;
  let manualTarget = null;
  let manualTargetChanged = null;

  function pickerText(value) {
    if (Array.isArray(value)) return value.map(v => String(v ?? '').trim()).filter(Boolean).join('、');
    if (value && typeof value === 'object') {
      try { return JSON.stringify(value); } catch (_) { return String(value); }
    }
    return String(value ?? '').replace(/\s+/g, ' ').trim();
  }

  function pickerFillText(value) {
    if (Array.isArray(value)) return value.map(v => String(v ?? '').trim()).filter(Boolean).join('、');
    if (value && typeof value === 'object') {
      try { return JSON.stringify(value, null, 2); } catch (_) { return String(value); }
    }
    return String(value ?? '').trim();
  }

  function manualTargetFromNode(node) {
    if (!(node instanceof Element)) return null;
    if (pickerHost && (node === pickerHost || pickerHost.contains(node))) return null;
    let el = node.closest?.('input, textarea, select, [role="combobox"], [contenteditable="true"]');
    if (!el) {
      const root = node.closest?.('.ant-select, .el-select, .arco-select, [class*="select"]');
      if (root) el = root.querySelector?.('input, [role="combobox"]') || root;
    }
    if (!el || !el.isConnected) return null;
    const type = (el.getAttribute?.('type') || '').toLowerCase();
    if (['hidden', 'button', 'submit', 'reset', 'file', 'password'].includes(type)) return null;
    return el;
  }

  function setManualTarget(node) {
    const next = manualTargetFromNode(node);
    if (!next) return;
    manualTarget = next;
    if (manualTargetChanged) manualTargetChanged(next);
  }

  document.addEventListener('focusin', event => setManualTarget(event.target), true);
  document.addEventListener('click', event => setManualTarget(event.target), true);

  function manualTargetLabel(el) {
    if (!el) return '尚未选择网页字段';
    const raw = clean(labelFor(el));
    const parts = raw.split('|').map(clean).filter(Boolean).filter(x => x.length <= 80);
    const preferred = parts.find(x => !/^(请输入|请选择|please\s*(input|select))/i.test(x));
    return preferred || parts[0] || clean(el.getAttribute?.('placeholder')) || clean(el.getAttribute?.('name')) || el.tagName.toLowerCase();
  }

  function focusableManualControls() {
    const selector = 'input, textarea, select, [role="combobox"], [contenteditable="true"]';
    const seen = new Set();
    const controls = [];
    for (const node of document.querySelectorAll(selector)) {
      if (!(node instanceof Element)) continue;
      if (pickerHost && (node === pickerHost || pickerHost.contains(node))) continue;
      if (!node.isConnected || !isVisible(node)) continue;
      if (node.matches?.(':disabled') || node.getAttribute?.('aria-disabled') === 'true') continue;

      const type = (node.getAttribute?.('type') || '').toLowerCase();
      if (['hidden', 'button', 'submit', 'reset', 'file', 'password'].includes(type)) continue;
      if ((node.tagName === 'INPUT' || node.tagName === 'TEXTAREA') && node.readOnly) continue;

      // Custom selects often expose both a wrapper/combobox and an inner input.
      // Keep only one usable focus target for the same visual control.
      const root = customSelectRoot(node);
      const key = root || node;
      if (seen.has(key)) continue;
      seen.add(key);

      let target = node;
      if (root && root !== node) {
        target = root.querySelector?.('input:not([type="hidden"]), [role="combobox"], select') || node;
      }
      controls.push({node: target, root: key});
    }
    return controls;
  }

  function sameManualControl(a, entry) {
    if (!a || !entry) return false;
    if (a === entry.node || a === entry.root) return true;
    try {
      if (entry.root?.contains?.(a) || a.contains?.(entry.node)) return true;
    } catch (_) {}
    return false;
  }

  function focusNextManualTarget(current) {
    const controls = focusableManualControls();
    if (!controls.length) return null;

    let index = controls.findIndex(entry => sameManualControl(current, entry));

    // For radio/checkbox groups, move past the whole group instead of focusing
    // another option in the same group.
    const currentType = (current?.getAttribute?.('type') || '').toLowerCase();
    const currentName = current?.getAttribute?.('name') || '';
    if (index >= 0 && currentName && ['radio', 'checkbox'].includes(currentType)) {
      while (
        index + 1 < controls.length &&
        controls[index + 1].node?.getAttribute?.('name') === currentName &&
        (controls[index + 1].node?.getAttribute?.('type') || '').toLowerCase() === currentType
      ) {
        index += 1;
      }
    }

    const nextEntry = index >= 0 ? controls[index + 1] : null;
    if (!nextEntry?.node) return null;

    const next = nextEntry.node;
    try { next.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'smooth'}); } catch (_) {
      try { next.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (_) {}
    }
    try { next.focus({preventScroll: true}); } catch (_) {
      try { next.focus(); } catch (_) {}
    }
    setManualTarget(next);
    return next;
  }

  async function chooseCustomSelectDirect(el, value) {
    const values = candidateValues(value).map(norm).filter(Boolean);
    const root = customSelectRoot(el) || el;
    try { root.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (_) {}
    try { root.click(); } catch (_) { try { el.click(); } catch (_) {} }
    await sleep(150);
    let options = visibleOptionNodes();
    if (!options.length) { await sleep(220); options = visibleOptionNodes(); }
    let best = null;
    for (const option of options) {
      const text = norm(clickableText(option));
      if (!text) continue;
      if (values.includes(text)) { best = option; break; }
      if (!best && values.some(v => v && (text.includes(v) || v.includes(text)))) best = option;
    }
    if (!best) {
      try { sendKey(el, 'Escape'); } catch (_) {}
      return false;
    }
    try { best.scrollIntoView({block: 'nearest'}); } catch (_) {}
    best.click();
    await sleep(120);
    return true;
  }

  async function fillManualTarget(value) {
    const el = manualTarget;
    if (!el || !el.isConnected) return {ok: false, reason: '请先点击招聘网页中要填写的输入框或下拉框。'};
    const raw = pickerFillText(value);
    if (!raw) return {ok: false, reason: '该本地数据为空。'};
    try {
      try { el.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (_) {}
      const type = (el.getAttribute?.('type') || '').toLowerCase();
      if (type === 'radio') {
        const group = el.name
          ? [...document.querySelectorAll('input[type="radio"]')].filter(x => x.name === el.name && isVisible(x))
          : [el];
        return {ok: chooseGroup(group, raw), reason: '未找到与该数据匹配的单选项。'};
      }
      if (type === 'checkbox') {
        const group = el.name
          ? [...document.querySelectorAll('input[type="checkbox"]')].filter(x => x.name === el.name && isVisible(x))
          : [];
        if (group.length > 1) return {ok: chooseGroup(group, raw), reason: '未找到与该数据匹配的复选项。'};
        const checked = ['是', 'yes', 'true', '1', '有', '接受'].includes(norm(raw));
        el.checked = checked;
        dispatch(el);
        return {ok: true};
      }
      if (dateLike(el, manualTargetLabel(el))) {
        const ok = await setDateControl(el, raw, manualTargetLabel(el));
        if (ok) return {ok: true};
      }
      if (el.tagName === 'SELECT') {
        const ok = chooseSelect(el, raw);
        return {ok, reason: ok ? '' : '下拉框中没有找到匹配选项。'};
      }
      const role = el.getAttribute?.('role');
      const selectRoot = customSelectRoot(el);
      if (role === 'combobox' || (selectRoot && /ant-select|el-select|arco-select|select/i.test(String(selectRoot.className || '')))) {
        const ok = await chooseCustomSelectDirect(el, raw);
        if (ok) return {ok: true};
        if (!(el.tagName === 'INPUT' && !el.readOnly)) return {ok: false, reason: '自定义下拉框中没有匹配选项。'};
      }
      if (el.getAttribute?.('contenteditable') === 'true') {
        el.focus();
        const current = String(el.textContent ?? '');
        el.textContent = current + raw;
        try {
          const range = document.createRange();
          range.selectNodeContents(el);
          range.collapse(false);
          const selection = window.getSelection();
          selection?.removeAllRanges();
          selection?.addRange(range);
        } catch (_) {}
        el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: raw}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        return {ok: true};
      }
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        appendNativeValue(el, raw);
        return {ok: String(el.value ?? '').endsWith(raw)};
      }
      const inner = el.querySelector?.('input, textarea');
      if (inner && isVisible(inner)) {
        appendNativeValue(inner, raw);
        return {ok: String(inner.value ?? '').endsWith(raw)};
      }
      return {ok: false, reason: '暂不支持这个网页控件。'};
    } catch (error) {
      return {ok: false, reason: error?.message || '填写失败'};
    }
  }

  function pushPickerItem(items, group, label, key, value) {
    const text = pickerText(value);
    if (!text) return;
    items.push({group, label, key, value, text});
  }

  function profilePickerItems(profile) {
    const items = [];
    const basicLabels = {
      name_cn: '姓名', name_en: '英文姓名', id_type: '证件类型', id_number: '证件号码', phone_country_code: '手机国家区号',
      phone: '手机号码', email: '电子邮箱', gender: '性别', birthday: '出生日期', age: '年龄', birth_place: '出生地',
      political_status: '政治面貌', party_join_date: '入党团时间', ethnicity: '民族',
      height_cm: '身高(cm)', weight_kg: '体重(kg)', hometown: '籍贯', is_beijing_household: '是否北京户口',
      household_location: '户口所在地', student_origin: '高考生源地', current_city: '现居城市',
      current_address: '现住址', marital_status: '婚姻情况', health_status: '健康状况', pre_enrollment_household_location: '入学前户口所在地',
      mailing_address: '通讯地址', postal_code: '邮政编码'
    };
    for (const [key, label] of Object.entries(basicLabels)) pushPickerItem(items, '基本信息', label, `basic.${key}`, profile.basic?.[key]);

    const eduLabels = {
      school: '学校名称', degree: '学历', academic_degree: '学位', college: '院系', major: '专业', research_direction: '研究方向', courses: '专业课程',
      start_date: '入学时间', end_date: '毕业时间', expected_degree_date: '拟取得学位时间',
      first_degree: '第一学位', full_time: '是否全日制', exchange_program: '合作交流项目',
      gpa: 'GPA', ranking: '专业/年级排名', education_type: '受教育类型',
      study_length_years: '学制', overseas_study_experience: '海外学习经历',
      school_country: '学校所属国家', is_main_study_experience: '是否主要学习经历',
      graduation_project: '毕业设计/论文'
    };
    (profile.education || []).forEach((record, index) => {
      const tag = clean(record?.degree || record?.school) || `第${index + 1}段`;
      for (const [key, label] of Object.entries(eduLabels)) pushPickerItem(items, `教育经历 · ${tag}`, label, `education[${index}].${key}`, record?.[key]);
    });

    const internLabels = {company: '工作单位', city: '所在城市', role: '岗位', start_date: '入职时间', end_date: '离职时间', contact_name: '联系人', contact_phone: '联系电话', description: '主要工作职责和业绩'};
    (profile.internships || []).forEach((record, index) => {
      const tag = clean(record?.company) || `第${index + 1}段`;
      for (const [key, label] of Object.entries(internLabels)) pushPickerItem(items, `实习经历 · ${tag}`, label, `internships[${index}].${key}`, record?.[key]);
    });

    const projectLabels = {
      name: '项目名称', type: '项目类型', role: '项目角色', start_date: '开始时间', end_date: '结束时间',
      tech_stack: '技术栈', description: '项目内容/描述', highlights: '项目亮点', result: '项目成果'
    };
    (profile.projects || []).forEach((record, index) => {
      const tag = clean(record?.name) || `第${index + 1}个项目`;
      for (const [key, label] of Object.entries(projectLabels)) pushPickerItem(items, `项目经历 · ${tag}`, label, `projects[${index}].${key}`, record?.[key]);
    });

    const campusLabels = {is_student_cadre: '是否为学生干部', start_date: '开始时间', end_date: '结束时间', description: '校园经历主要内容'};
    for (const [key, label] of Object.entries(campusLabels)) pushPickerItem(items, '校园经历', label, `campus_experience.${key}`, profile.campus_experience?.[key]);

    const skillLabels = {cet4: 'CET4', cet6: 'CET6', tem4: 'TEM4', tem8: 'TEM8', other_language: '其他外语', computer_level: '计算机水平', certificates: '技能证书'};
    for (const [key, label] of Object.entries(skillLabels)) pushPickerItem(items, '技能水平', label, `skills.${key}`, profile.skills?.[key]);

    const awardLabels = {date: '获奖时间', name: '奖项名称', level: '奖项级别', type: '奖项类型', reference: '参考信息', details: '详细说明'};
    (profile.awards || []).forEach((record, index) => {
      const tag = clean(record?.name) || `第${index + 1}条`;
      for (const [key, label] of Object.entries(awardLabels)) pushPickerItem(items, `获奖经历 · ${tag}`, label, `awards[${index}].${key}`, record?.[key]);
    });

    const familyLabels = {relation: '与本人关系', name: '亲属姓名', age: '年龄', employer: '工作单位', department: '工作部门', position: '职务', phone: '联系电话', political_status: '政治面貌', is_china_post_employee: '是否为中国邮政系统职工'};
    (profile.family?.members || []).forEach((record, index) => {
      const tag = clean(record?.relation || record?.name) || `第${index + 1}位`;
      for (const [key, label] of Object.entries(familyLabels)) pushPickerItem(items, `家庭关系 · ${tag}`, label, `family.members[${index}].${key}`, record?.[key]);
    });
    pushPickerItem(items, '家庭关系', '是否有招商局/招商银行近亲属', 'family.has_relative_in_cmb_group', profile.family?.has_relative_in_cmb_group);
    const emergencyLabels = {name: '紧急联系人姓名', employer: '紧急联系人单位', position: '紧急联系人职务', phone: '紧急联系人电话'};
    for (const [key, label] of Object.entries(emergencyLabels)) pushPickerItem(items, '紧急联系人', label, `family.emergency_contact.${key}`, profile.family?.emergency_contact?.[key]);

    pushPickerItem(items, '个人描述', '自我评价', 'self_evaluation.content', profile.self_evaluation?.content);
    pushPickerItem(items, '个人描述', '性格词', 'personality.words', profile.personality?.words);
    pushPickerItem(items, '求职偏好', '意向城市', 'job_preferences.cities', profile.job_preferences?.cities);
    pushPickerItem(items, '求职偏好', '意向岗位', 'job_preferences.job_types', profile.job_preferences?.job_types);
    pushPickerItem(items, '求职偏好', '期望薪资', 'job_preferences.salary', profile.job_preferences?.salary);
    pushPickerItem(items, '求职偏好', '接受地点调剂', 'job_preferences.accept_location_transfer', profile.job_preferences?.accept_location_transfer);

    const summaryLabels = {education_text: '教育经历汇总', internships_text: '实习经历汇总', projects_text: '项目/科研经历汇总', student_activities_text: '校园/社团经历汇总', awards_text: '获奖经历汇总', skills_text: '技能汇总', personality_text: '性格描述'};
    for (const [key, label] of Object.entries(summaryLabels)) pushPickerItem(items, '长文本', label, `summaries.${key}`, profile.summaries?.[key]);
    return items;
  }

  function closeFieldPicker() {
    if (pickerHost?.isConnected) pickerHost.remove();
    pickerHost = null;
    manualTargetChanged = null;
  }

  function pickerCss() {
    return `
      :host{all:initial}*{box-sizing:border-box}
      .ja-panel{position:fixed;right:18px;top:18px;width:min(440px,calc(100vw - 36px));max-height:calc(100vh - 36px);z-index:2147483647;background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,.22);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;display:flex;flex-direction:column;overflow:hidden}
      .ja-head{padding:14px;border-bottom:1px solid #e5e7eb}.ja-title-row{display:flex;justify-content:space-between;gap:12px}.ja-title{font-size:17px;font-weight:700}.ja-close{border:0;background:transparent;color:#6b7280;font-size:22px;cursor:pointer}.ja-help{font-size:12px;color:#6b7280;line-height:1.5;margin-top:5px}.ja-target{margin-top:9px;padding:8px 10px;border-radius:8px;background:#f3f4f6;color:#374151;font-size:12px;line-height:1.4}.ja-target.ready{background:#ecfdf5;color:#166534}.ja-search{margin-top:9px;width:100%;border:1px solid #d1d5db;border-radius:8px;padding:9px 10px;font:inherit;color:#111827;background:#fff;outline:none}.ja-search:focus{border-color:#111827}.ja-status{font-size:12px;color:#4b5563;margin-top:8px;min-height:17px;line-height:1.4}
      .ja-list{overflow:auto;padding:9px 10px 12px;background:#f9fafb;overscroll-behavior:contain}.ja-row{width:100%;display:block;text-align:left;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:10px;margin-bottom:8px;cursor:pointer;color:#111827}.ja-row:hover,.ja-row:focus{border-color:#111827;outline:none}.ja-row.ok{border-color:#22c55e;background:#f0fdf4}.ja-row.fail{border-color:#ef4444;background:#fef2f2}.ja-group{font-size:10px;color:#9ca3af;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ja-label{font-size:13px;font-weight:650;margin-top:2px}.ja-value{font-size:12px;color:#374151;margin-top:4px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;word-break:break-all}.ja-key{font-size:10px;color:#9ca3af;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ja-empty{padding:22px 12px;text-align:center;color:#6b7280;background:#fff;border:1px dashed #d1d5db;border-radius:10px}
      @media(max-width:520px){.ja-panel{right:8px;top:8px;width:calc(100vw - 16px);max-height:calc(100vh - 16px)}}
    `;
  }

  async function openFieldPicker() {
    closeFieldPicker();
    const response = await fetch(`${API}/api/profile`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`本地服务返回 ${response.status}`);
    const data = await response.json();
    const items = profilePickerItems(data.profile || {});

    const host = document.createElement('div');
    host.id = 'job-autofill-field-picker-host';
    document.documentElement.appendChild(host);
    pickerHost = host;
    const shadow = host.attachShadow({mode: 'open'});
    const style = document.createElement('style');
    style.textContent = pickerCss();
    shadow.appendChild(style);

    const panel = document.createElement('section');
    panel.className = 'ja-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', '本地数据快捷填入');
    shadow.appendChild(panel);

    const head = document.createElement('div');
    head.className = 'ja-head';
    panel.appendChild(head);
    const titleRow = document.createElement('div');
    titleRow.className = 'ja-title-row';
    head.appendChild(titleRow);
    const titleBox = document.createElement('div');
    titleRow.appendChild(titleBox);
    const title = document.createElement('div');
    title.className = 'ja-title';
    title.textContent = '本地数据快捷填入';
    titleBox.appendChild(title);
    const help = document.createElement('div');
    help.className = 'ja-help';
    help.textContent = '无需扫描。先点击招聘网页中要填写的字段，再点下面一条本地数据；填写成功后会自动跳到下一个可填写字段。';
    titleBox.appendChild(help);
    const close = document.createElement('button');
    close.type = 'button'; close.className = 'ja-close'; close.textContent = '×'; close.setAttribute('aria-label', '关闭');
    close.addEventListener('click', closeFieldPicker); titleRow.appendChild(close);

    const targetBox = document.createElement('div');
    targetBox.className = 'ja-target';
    head.appendChild(targetBox);
    const status = document.createElement('div');
    status.className = 'ja-status';
    status.textContent = `已加载 ${items.length} 条本地数据。`;
    head.appendChild(status);
    const search = document.createElement('input');
    search.type = 'search'; search.className = 'ja-search'; search.placeholder = '搜索姓名、学校、单位、奖项、电话…';
    head.appendChild(search);

    const list = document.createElement('div');
    list.className = 'ja-list';
    panel.appendChild(list);

    function updateTarget() {
      if (manualTarget?.isConnected) {
        targetBox.classList.add('ready');
        targetBox.textContent = `当前目标：${manualTargetLabel(manualTarget)}`;
      } else {
        targetBox.classList.remove('ready');
        targetBox.textContent = '当前目标：请先点击招聘网页中的输入框 / 下拉框';
      }
    }
    manualTargetChanged = updateTarget;
    updateTarget();

    const rows = [];
    for (const item of items) {
      const row = document.createElement('button');
      row.type = 'button'; row.className = 'ja-row';
      row.dataset.search = norm(`${item.group} ${item.label} ${item.text} ${item.key}`);
      const group = document.createElement('div'); group.className = 'ja-group'; group.textContent = item.group; row.appendChild(group);
      const label = document.createElement('div'); label.className = 'ja-label'; label.textContent = item.label; row.appendChild(label);
      const value = document.createElement('div'); value.className = 'ja-value'; value.textContent = item.text; row.appendChild(value);
      const key = document.createElement('div'); key.className = 'ja-key'; key.textContent = item.key; row.appendChild(key);
      row.addEventListener('click', async () => {
        row.disabled = true; row.classList.remove('ok', 'fail');
        const targetBeforeFill = manualTarget;
        const targetName = manualTargetLabel(targetBeforeFill);
        const result = await fillManualTarget(item.value);
        if (result.ok) {
          row.classList.add('ok');
          const next = focusNextManualTarget(targetBeforeFill);
          const nextText = next ? `；已跳到下一项“${manualTargetLabel(next)}”` : '；已到当前页面最后一个可填写字段';
          status.textContent = `已填入“${targetName}”：${item.label} = ${item.text.slice(0, 90)}${item.text.length > 90 ? '…' : ''}${nextText}`;
        } else {
          row.classList.add('fail');
          status.textContent = result.reason || '填写失败。';
        }
        row.disabled = false;
      });
      list.appendChild(row); rows.push(row);
    }
    if (!items.length) {
      const empty = document.createElement('div'); empty.className = 'ja-empty'; empty.textContent = '本地档案没有可展示的数据。'; list.appendChild(empty);
    }

    search.addEventListener('input', () => {
      const q = norm(search.value);
      let visible = 0;
      for (const row of rows) {
        const show = !q || row.dataset.search.includes(q);
        row.style.display = show ? 'block' : 'none';
        if (show) visible += 1;
      }
      status.textContent = q ? `搜索结果 ${visible} 条。` : `已加载 ${items.length} 条本地数据。`;
    });

    return {total: items.length, matched: items.length};
  }

  async function run(useAi) {
    const fields = scanFields();
    const response = await fetch(`${API}/api/match`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({page_url: location.href, fields, use_ai: !!useAi}),
    });
    if (!response.ok) throw new Error(`本地服务返回 ${response.status}`);
    const data = await response.json();
    let filled = 0;
    for (const match of data.matches || []) {
      if (fillOne(match)) filled += 1;
    }

    let profile = {};
    try {
      const p = await fetch(`${API}/api/profile`, {cache: 'no-store'});
      if (p.ok) profile = (await p.json()).profile || {};
    } catch (_) {}

    const internships = await fillRepeatableCollection('internships', profile.internships || [], !!useAi);
    // A failed editor is normally still open. Never let the next collection write into it.
    const projects = internships.stopped && internships.failed > 0
      ? blockedRepeatable('projects', profile.projects || [], 'blocked-by-prior-repeatable-failure')
      : await fillRepeatableCollection('projects', profile.projects || [], !!useAi);
    const beforeAwardsFailed = (internships.stopped && internships.failed > 0) || (projects.stopped && projects.failed > 0);
    const awards = beforeAwardsFailed
      ? blockedRepeatable('awards', profile.awards || [], 'blocked-by-prior-repeatable-failure')
      : await fillRepeatableCollection('awards', profile.awards || [], !!useAi);
    const priorFailed = beforeAwardsFailed || (awards.stopped && awards.failed > 0);
    const family = priorFailed
      ? blockedRepeatable('family', profile.family?.members || [], 'blocked-by-prior-repeatable-failure')
      : await fillRepeatableCollection('family', profile.family?.members || [], !!useAi);

    return {...data.stats, filled, repeatable: {internships, projects, awards, family}};
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === 'JOB_AUTOFILL_SCAN_AND_FILL') {
      run(message.useAi)
        .then(stats => sendResponse({ok: true, stats}))
        .catch(err => sendResponse({ok: false, error: err.message || String(err)}));
      return true;
    }
    if (message?.type === 'JOB_AUTOFILL_OPEN_PICKER') {
      openFieldPicker()
        .then(stats => sendResponse({ok: true, stats}))
        .catch(err => sendResponse({ok: false, error: err.message || String(err)}));
      return true;
    }
  });

  // Test hook is intentionally exposed only on the bundled localhost demo page.
  if (location.hostname === '127.0.0.1' || location.hostname === 'localhost') {
    window.__JOB_AUTOFILL_TEST__ = {run, openFieldPicker, findSection, fillRepeatableCollection};
  }
})();
