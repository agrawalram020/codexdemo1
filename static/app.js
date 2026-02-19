const $ = (id) => document.getElementById(id);
let chart;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function taskCard(task) {
  const tpl = $('taskCardTemplate').content.firstElementChild.cloneNode(true);
  tpl.dataset.id = task.id;
  tpl.querySelector('.task-title').textContent = task.title;
  tpl.querySelector('.frequency').textContent = task.frequency;
  tpl.querySelector('.meta').textContent = `${task.category} ${task.due_date ? `• due ${task.due_date}` : ''}`;
  tpl.querySelector('.notes').textContent = task.notes || 'No notes yet';
  tpl.querySelector('.progress-bar').style.width = `${task.progress}%`;

  tpl.querySelector('.delete-btn').onclick = async () => {
    await api(`/api/tasks/${task.id}`, { method: 'DELETE' });
    await refreshAll();
  };
  tpl.querySelector('.log-btn').onclick = async () => {
    await api(`/api/tasks/${task.id}/log`, { method: 'POST', body: JSON.stringify({}) });
    await refreshAll();
  };
  return tpl;
}

async function loadTasks() {
  const tasks = await api('/api/tasks');
  $('todoList').innerHTML = '';
  $('doneList').innerHTML = '';
  tasks.forEach((task) => (task.completed ? $('doneList') : $('todoList')).appendChild(taskCard(task)));
}

async function loadGoal() {
  const goal = await api('/api/goal');
  if (!goal.title) return;
  $('goalTitle').value = goal.title;
  $('goalDescription').value = goal.description;
  $('goalStart').value = goal.start_date;
  $('goalEnd').value = goal.end_date;
  $('goalTimeline').innerHTML = `<p><strong>${goal.timeline_progress}% timeline elapsed</strong></p>`;
}

async function loadDashboard() {
  const stats = await api('/api/dashboard');
  $('totalTasks').textContent = stats.total_tasks;
  $('completedTasks').textContent = stats.completed_tasks;
  $('completionRate').textContent = `${stats.completion_rate}%`;
  $('avgProgress').textContent = `${stats.avg_progress}%`;

  const labels = stats.daily_series.map((x) => x.date.slice(5));
  const values = stats.daily_series.map((x) => x.count);
  if (chart) chart.destroy();
  chart = new Chart($('trendChart'), {
    type: 'line',
    data: { labels, datasets: [{ label: 'Daily task logs', data: values, borderColor: '#5ad0ff', tension: 0.3 }] },
    options: { scales: { y: { beginAtZero: true, ticks: { color: '#c8d8ff' } }, x: { ticks: { color: '#c8d8ff' } } } },
  });
}

async function refreshAll() {
  await Promise.all([loadTasks(), loadGoal(), loadDashboard()]);
}

function setupSortables() {
  const shared = {
    group: 'tasks',
    animation: 150,
    onEnd: async (evt) => {
      const column = evt.to.id;
      const ids = [...evt.to.children].map((card) => Number(card.dataset.id));
      await api('/api/tasks/reorder', {
        method: 'POST',
        body: JSON.stringify({ ordered_ids: ids, completed: column === 'doneList' }),
      });
      await refreshAll();
    },
  };
  new Sortable($('todoList'), shared);
  new Sortable($('doneList'), shared);
}

$('taskForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  await api('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({
      title: $('taskTitle').value,
      frequency: $('taskFrequency').value,
      category: $('taskCategory').value,
      due_date: $('taskDue').value || null,
      progress: Number($('taskProgress').value || 0),
      notes: $('taskNotes').value,
    }),
  });
  e.target.reset();
  await refreshAll();
});

$('goalForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  await api('/api/goal', {
    method: 'POST',
    body: JSON.stringify({
      title: $('goalTitle').value,
      description: $('goalDescription').value,
      start_date: $('goalStart').value,
      end_date: $('goalEnd').value,
    }),
  });
  await refreshAll();
});

$('reminderBtn').onclick = async () => {
  const result = await api('/api/reminders/test', { method: 'POST', body: JSON.stringify({}) });
  alert(`Reminder status\nEmail: ${result.email}\nTelegram: ${result.telegram}\nWhatsApp: ${result.whatsapp}`);
};

setupSortables();
refreshAll();
