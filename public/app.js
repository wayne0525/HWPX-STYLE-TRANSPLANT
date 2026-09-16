'use strict';
const $ = id => document.getElementById(id);
let state = null;
let downloadURL = null;
let busy = false;
const esc = value => String(value ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));

function status(message, error = false) {
  const el = $('status');
  el.style.display = 'block';
  el.textContent = message;
  el.classList.toggle('error', error);
}

function clearDownload() {
  if (downloadURL) URL.revokeObjectURL(downloadURL);
  downloadURL = null;
  const dl = $('downloadLink');
  dl.removeAttribute('href');
  dl.removeAttribute('download');
  dl.style.display = 'none';
}

function hideProgress() {
  $('progress').style.display = 'none';
}

function progress(pct, stage) {
  $('progress').style.display = 'block';
  const clamped = Math.min(100, Math.max(0, Math.floor(pct)));
  $('progressBar').style.width = clamped + '%';
  $('progressStage').textContent = stage;
  $('progressPct').textContent = clamped + '%';
}

function invalidate() {
  state = null;
  clearDownload();
  hideProgress();
  $('status').style.display = 'none';
}

function lock(value) {
  busy = value;
  document.querySelectorAll('button, input, textarea').forEach(el => {
    el.disabled = value || el.dataset.protected === 'true';
  });
}

async function request(payload) {
  const body = JSON.stringify(payload);
  if (new TextEncoder().encode(body).length > 3800000) throw new Error('전송할 데이터가 너무 큽니다 원문 크기를 줄여 주세요');
  const response = await fetch('/api/transplant', { method:'POST', headers:{'Content-Type':'application/json'}, body });
  const data = await response.json().catch(() => { throw new Error('서버 응답을 읽지 못했습니다'); });
  if (!response.ok) throw new Error(data.message || '서버 요청 실패');
  return data;
}

function base64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = () => reject(new Error('파일을 읽지 못했습니다'));
    reader.readAsDataURL(file);
  });
}

async function run() {
  if (busy) return;
  invalidate();
  lock(true);
  try {
    const aFile = $('fileA').files[0];
    const bFile = $('fileB').files[0];
    const text = $('sourceText').value;
    if (!aFile || (!bFile && !text.trim())) throw new Error('A 양식과 B 내용을 넣어 주세요');
    if (bFile && text.trim()) throw new Error('B 파일과 붙여넣기 중 하나만 사용해 주세요');
    if (aFile.size + (bFile ? bFile.size : new TextEncoder().encode(text).length) > 2500000) throw new Error('A와 B 합계는 2.5MB 이하여야 합니다');

    const aBase64 = await base64(aFile);
    const a = { name: aFile.name, base64: aBase64 };
    const b = bFile
      ? { name: bFile.name, kind: bFile.name.toLowerCase().split('.').pop(), base64: await base64(bFile) }
      : { kind: 'txt', text };

    progress(5, '파일 읽기');
    progress(15, '양식의 입력란을 분석하고 있습니다');
    const analysis = await request({ action: 'analyze', a, b });
    state = {
      a, b,
      hash: analysis.analysis.a_hash,
      fields: analysis.analysis.fields,
      proposals: [],
      manual: new Set(),
    };

    progress(35, '분석 완료 · 내용을 제안받고 있습니다');
    const unresolved = state.fields.filter(f => f.editable && !state.proposals.some(p => p.fieldId === f.fieldId));
    if (unresolved.length > 0) {
      const batchSize = 20;
      const total = unresolved.length;
      const batches = Math.ceil(total / batchSize);
      let completed = 0;
      for (let i = 0; i < unresolved.length; i += batchSize) {
        const slice = unresolved.slice(i, i + batchSize);
        const suggested = await request({ action: 'suggest', fields: slice, blocks: analysis.source.blocks });
        state.proposals.push(...(suggested.suggestions || []));
        completed++;
        const doneCount = Math.min(i + batchSize, total);
        const pct = 35 + Math.round((completed / batches) * 40);
        progress(pct, `내용 제안 · ${doneCount}/${total} 완료`);
      }
    }

    progress(75, '내용 제안 완료 · 기입과 검증을 진행 중입니다');
    const edits = state.fields.map(f => {
      const proposal = state.proposals.find(p => p.fieldId === f.fieldId);
      const value = proposal ? proposal.value : '';
      const origin = state.manual.has(f.fieldId) || !proposal ? 'manual' : (proposal.origin || 'solar');
      return {
        fieldId: f.fieldId,
        value,
        selected: !!proposal,
        origin,
      };
    });

    progress(85, '선택된 내용을 기입하고 결과 구조를 검증하고 있습니다');
    const data = await request({
      action: 'generate',
      a: state.a,
      b: state.b,
      aHash: state.hash,
      edits,
      suggestions: state.proposals,
    });

    const bytes = Uint8Array.from(atob(data.result.resultBytes), c => c.charCodeAt(0));
    const changed = (data.result.changedFields || []).length;
    const editableCount = state.fields.filter(f => f.editable).length;
    const notFilled = editableCount - changed;

    if (changed > 0) {
      downloadURL = URL.createObjectURL(new Blob([bytes], { type: 'application/vnd.hancom.hwpx' }));
      const dl = $('downloadLink');
      dl.href = downloadURL;
      dl.download = state.a.name.replace(/\.hwpx$/i, '') + '_작성본.hwpx';
      dl.style.display = 'inline-block';
      progress(100, `완료 · 기입 ${changed}개 · 미기입 ${notFilled}개`);
      status(`작성본을 생성했습니다 · 기입 ${changed}개 · 미기입 ${notFilled}개`);
    } else {
      progress(85, '기입할 내용이 없습니다');
      status('기입할 내용이 없습니다 · 작성본을 생성하지 않았습니다');
    }
  } catch (error) {
    status(error.message, true);
  } finally {
    lock(false);
  }
}

$('runBtn').addEventListener('click', run);
$('resetBtn').addEventListener('click', () => {
  invalidate();
  $('fileA').value = '';
  $('fileB').value = '';
  $('sourceText').value = '';
});
['fileA', 'fileB', 'sourceText'].forEach(id => $(id).addEventListener('input', invalidate));
