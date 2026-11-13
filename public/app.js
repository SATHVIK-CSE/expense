const list = document.querySelector('#expense-list');
const empty = document.querySelector('#empty-state');
const modal = document.querySelector('#modal');
const form = document.querySelector('#expense-form');
const searchInput = document.querySelector('#search');
const categoryFilter = document.querySelector('#category-filter');
const authScreen = document.querySelector('#auth-screen');
const appLayout = document.querySelector('#app-layout');
const authForm = document.querySelector('#auth-form');
const currency = new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' });
let expenses = [];
let toastTimer;
let authMode = 'login';

const localDate = (date) => {
  const d = new Date(`${date}T00:00:00`);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};
function showToast(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
}
function showSignedOut() {
  appLayout.classList.add('auth-hidden');
  authScreen.hidden = false;
}
function showSignedIn(username) {
  authScreen.hidden = true;
  appLayout.classList.remove('auth-hidden');
  document.querySelector('#profile-username').textContent = username;
  document.querySelector('#user-avatar').textContent = username.slice(0, 2).toUpperCase();
  document.querySelector('.avatar').textContent = username.slice(0, 2).toUpperCase();
}
function setAuthMode(mode) {
  authMode = mode;
  const registering = mode === 'register';
  document.querySelector('#auth-title').textContent = registering ? 'Create your account' : 'Welcome back';
  document.querySelector('#auth-intro').textContent = registering
    ? 'Choose a username and password to start your private expense list.'
    : 'Sign in to see your own expenses.';
  document.querySelector('#auth-submit').innerHTML = registering ? 'Create account <span>→</span>' : 'Sign in <span>→</span>';
  document.querySelector('#auth-switch-copy').textContent = registering ? 'Already have an account?' : 'New here?';
  document.querySelector('#auth-switch').textContent = registering ? 'Sign in' : 'Create an account';
  authForm.elements.password.autocomplete = registering ? 'new-password' : 'current-password';
  authForm.elements.password.setAttribute('minlength', registering ? '10' : '1');
  document.querySelector('#auth-error').textContent = '';
}
function render() {
  const term = searchInput.value.trim().toLowerCase();
  const category = categoryFilter.value;
  const visible = expenses.filter((item) => {
    const matchesText = `${item.title} ${item.note}`.toLowerCase().includes(term);
    return matchesText && (category === 'All' || item.category === category);
  });
  list.replaceChildren();
  for (const item of visible) {
    const row = document.createElement('tr');
    const description = document.createElement('td');
    const title = document.createElement('div');
    title.className = 'expense-title';
    title.textContent = item.title;
    description.append(title);
    if (item.note) {
      const note = document.createElement('div');
      note.className = 'expense-note';
      note.textContent = item.note;
      description.append(note);
    }
    const categoryCell = document.createElement('td');
    const pill = document.createElement('span');
    pill.className = `category-pill ${item.category.toLowerCase()}`;
    pill.textContent = item.category;
    categoryCell.append(pill);
    const date = document.createElement('td');
    date.textContent = localDate(item.expense_date);
    const amount = document.createElement('td');
    amount.className = 'amount';
    amount.textContent = `− ${currency.format(item.amount)}`;
    const action = document.createElement('td');
    const remove = document.createElement('button');
    remove.className = 'delete-btn';
    remove.type = 'button';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `Delete ${item.title}`);
    remove.addEventListener('click', () => deleteExpense(item.id));
    action.append(remove);
    row.append(description, categoryCell, date, amount, action);
    list.append(row);
  }
  empty.classList.toggle('visible', visible.length === 0);
  document.querySelector('#result-count').textContent = `Showing ${visible.length} expense${visible.length === 1 ? '' : 's'}`;
  const total = expenses.reduce((sum, item) => sum + Number(item.amount), 0);
  const today = new Date();
  const monthTotal = expenses.filter((item) => {
    const d = new Date(`${item.expense_date}T00:00:00`);
    return d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth();
  }).reduce((sum, item) => sum + Number(item.amount), 0);
  document.querySelector('#total-value').textContent = currency.format(total);
  document.querySelector('#month-value').textContent = currency.format(monthTotal);
  document.querySelector('#count-value').textContent = expenses.length.toLocaleString();
}
async function loadExpenses() {
  try {
    const response = await fetch('/api/expenses');
    if (response.status === 401) return showSignedOut();
    if (!response.ok) throw new Error('Could not load expenses.');
    expenses = await response.json();
    render();
  } catch (error) {
    showToast(error.message || 'Could not connect to the server.');
  }
}
async function deleteExpense(id) {
  if (!window.confirm('Delete this expense?')) return;
  try {
    const response = await fetch(`/api/expenses/${id}`, { method: 'DELETE' });
    if (response.status === 401) return showSignedOut();
    if (!response.ok) throw new Error('Could not delete expense.');
    expenses = expenses.filter((item) => item.id !== id);
    render();
    showToast('Expense deleted.');
  } catch (error) {
    showToast(error.message || 'Could not connect to the server.');
  }
}
function openModal() {
  form.reset();
  form.elements.expense_date.value = new Date().toISOString().slice(0, 10);
  document.querySelector('#form-error').textContent = '';
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  form.elements.title.focus();
}
function closeModal() {
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
}

document.querySelector('#today').textContent = new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
document.querySelector('#open-form').addEventListener('click', openModal);
document.querySelector('#empty-add').addEventListener('click', openModal);
document.querySelector('#close-form').addEventListener('click', closeModal);
document.querySelector('#cancel-form').addEventListener('click', closeModal);
document.querySelector('#refresh').addEventListener('click', loadExpenses);
document.querySelector('#auth-switch').addEventListener('click', () => setAuthMode(authMode === 'login' ? 'register' : 'login'));
document.querySelector('#logout').addEventListener('click', async () => {
  await fetch('/api/auth/logout', { method: 'POST' });
  expenses = [];
  render();
  setAuthMode('login');
  showSignedOut();
});
searchInput.addEventListener('input', render);
categoryFilter.addEventListener('change', render);
modal.addEventListener('click', (event) => { if (event.target === modal) closeModal(); });
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeModal(); });

authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(authForm);
  const errorBox = document.querySelector('#auth-error');
  errorBox.textContent = '';
  try {
    const response = await fetch(`/api/auth/${authMode}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: data.get('username').trim(), password: data.get('password') }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail[0].msg : result.detail || 'Could not sign in.');
    authForm.reset();
    showSignedIn(result.username);
    await loadExpenses();
  } catch (error) {
    errorBox.textContent = error.message || 'Could not connect to the server.';
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const payload = {
    title: data.get('title').trim(), amount: Number(data.get('amount')), category: data.get('category'),
    expense_date: data.get('expense_date'), note: data.get('note').trim(),
  };
  const errorBox = document.querySelector('#form-error');
  errorBox.textContent = '';
  try {
    const response = await fetch('/api/expenses', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (response.status === 401) return showSignedOut();
    if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail[0].msg : result.detail || 'Could not save expense.');
    expenses.unshift(result);
    expenses.sort((a, b) => b.expense_date.localeCompare(a.expense_date) || b.id - a.id);
    render();
    closeModal();
    showToast('Expense saved.');
  } catch (error) {
    errorBox.textContent = error.message || 'Could not connect to the server.';
  }
});

async function start() {
  setAuthMode('login');
  try {
    const response = await fetch('/api/auth/me');
    if (!response.ok) return showSignedOut();
    const account = await response.json();
    showSignedIn(account.username);
    await loadExpenses();
  } catch {
    showSignedOut();
    document.querySelector('#auth-error').textContent = 'Could not connect to the server.';
  }
}
start();
