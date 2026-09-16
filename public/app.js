'use strict';
const $ = id => document.getElementById(id);
let state = null;
let downloadURL = null;
let busy = false;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function status(message, error = false) {
  $('status').style.display = 'block';
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}
function clearDownload() {
  if (downloadURL) URL.revokeObjectURL(downloadURL);
  downloadURL = null;
  $('downloadLink').removeAttribute('href');
  $('result').style.display = 'none';
}
function invalidate() {
  state = null;
  clearDownload();
  $('review').hidden = true;
  $('fields').replaceChildren();
  $('status').style.display = 'none';
}
function lock(value) {
  busy = value;
  document.querySelectorAll('button,input,textarea').forEach(el => { el.disabled = value || el.dataset.protected === 'true'; });
}
async function request(payload) {
  const body = JSON.stringify(payload);
  if (new TextEncoder().encode(body).length > 3800000) throw new Error('전송할 데이터가 너무 큽니다 원문 크기를 줄여 주세요');
  const response = await fetch('/api/transplant', {method:'POST', headers:{'Content-Type':'application/json'}, body});
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
function renderFields() {
  $('fields').innerHTML = state.fields.map((field, i) => {
    const proposal = state.proposals.find(p => p.fieldId === field.fieldId);
    const location = field.location || {};
    const position = [location.section?.path, location.table && '표 ' + (location.table.tableIndex + 1),
      location.row && '행 ' + (location.row.rowIndex + 1), location.column && '열 ' + (location.column.columnIndex + 1)].filter(Boolean).join(' · ');
    return '<div class="field"><label for="value-' + i + '">' + esc(field.label || '입력란') + '</label>' +
      '<div class="hint">' + esc(position) + '</div>' +
      '<label><input type="checkbox" id="select-' + i + '" ' + (!field.editable ? 'disabled data-protected="true"' : '') + '> 이 칸 채우기</label>' +
      '<textarea style="width:100%" rows="2" id="value-' + i + '" ' + (!field.editable ? 'disabled data-protected="true"' : '') + '>' + esc(proposal?.value || '') + '</textarea>' +
      '<div class="hint">' + esc(!field.editable ? '보호된 칸 · 자동 편집 불가' : proposal ? '근거: ' + proposal.evidenceQuote : '제안 없음 · 직접 입력 가능') + '</div></div>';
  }).join('');
  state.fields.forEach((field, i) => {
    $('value-' + i).addEventListener('input', () => { state.manual.add(field.fieldId); clearDownload(); });
    $('select-' + i).addEventListener('change', clearDownload);
  });
  $('review').hidden = false;
}
async function analyze() {
  if (busy) return;
  invalidate();
  lock(true);
  try {
    const aFile = $('fileA').files[0], bFile = $('fileB').files[0], text = $('sourceText').value;
    if (!aFile || (!bFile && !text.trim())) throw new Error('A 양식과 B 내용을 넣어 주세요');
    if (bFile && text.trim()) throw new Error('B 파일과 붙여넣기 중 하나만 사용해 주세요');
    if (aFile.size + (bFile?.size || new TextEncoder().encode(text).length) > 2500000) throw new Error('A와 B 합계는 2.5MB 이하여야 합니다');
    const a = {name:aFile.name, base64:await base64(aFile)};
    const b = bFile ? {name:bFile.name, kind:bFile.name.toLowerCase().split('.').pop(), base64:await base64(bFile)} : {kind:'txt', text};
    status('양식의 입력란과 원문을 분석하고 있습니다');
    const data = await request({action:'analyze', a, b});
    state = {a, b, hash:data.analysis.a_hash, fields:data.analysis.fields, proposals:data.suggestions, manual:new Set()};
    const warnings = [...(data.warnings || [])];
    const unresolved = state.fields.filter(f => f.editable && !state.proposals.some(p => p.fieldId === f.fieldId));
    for (let i = 0; i < unresolved.length; i += 20) {
      status('Solar 내용 제안 중 · ' + Math.min(i + 20, unresolved.length) + '/' + unresolved.length);
      try {
        const suggested = await request({action:'suggest', fields:unresolved.slice(i, i + 20), blocks:data.source.blocks});
        state.proposals.push(...suggested.suggestions);
        warnings.push(...suggested.warnings);
        if (suggested.warnings.some(w => w.includes('API 키가 없어'))) break;
      } catch (error) { warnings.push(error.message); break; }
    }
    $('warnings').textContent = [...new Set(warnings)].join('\n');
    renderFields();
    status(state.fields.length ? '분석 완료 · 내용과 근거를 확인하고 채울 칸을 선택하세요' : '입력란을 찾지 못했습니다 다른 양식을 확인해 주세요');
  } catch (error) { status(error.message, true); }
  finally { lock(false); }
}
async function generate() {
  if (busy || !state) return;
  clearDownload();
  const edits = state.fields.filter(f => f.editable).map(f => {
    const index = state.fields.indexOf(f);
    const proposal = state.proposals.find(p => p.fieldId === f.fieldId);
    return {fieldId:f.fieldId, value:$('value-' + index).value, selected:$('select-' + index).checked,
      origin:state.manual.has(f.fieldId) || !proposal ? 'manual' : proposal.origin || 'solar'};
  });
  lock(true);
  status('선택한 내용을 기입하고 결과 구조를 검사하고 있습니다');
  try {
    const data = await request({action:'generate', a:state.a, b:state.b, aHash:state.hash, edits, suggestions:state.proposals});
    const bytes = Uint8Array.from(atob(data.result.resultBytes), c => c.charCodeAt(0));
    downloadURL = URL.createObjectURL(new Blob([bytes], {type:'application/vnd.hancom.hwpx'}));
    $('downloadLink').href = downloadURL;
    $('downloadLink').download = state.a.name.replace(/\.hwpx$/i, '') + '_작성본.hwpx';
    $('resultSummary').textContent = '기입 ' + data.result.changedFields.length + '개 · 구조 검증 통과\n' + (data.result.warnings || []).map(w => w.message).join('\n');
    $('result').style.display = 'block';
    status('작성본을 생성했습니다');
  } catch (error) { status(error.message, true); }
  finally { lock(false); }
}
$('runBtn').addEventListener('click', analyze);
$('generateBtn').addEventListener('click', generate);
$('resetBtn').addEventListener('click', () => { invalidate(); $('fileA').value = ''; $('fileB').value = ''; $('sourceText').value = ''; });
['fileA', 'fileB', 'sourceText'].forEach(id => $(id).addEventListener('input', invalidate));
