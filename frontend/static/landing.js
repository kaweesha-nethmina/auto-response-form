document.getElementById('year').textContent = new Date().getFullYear();
const count = document.getElementById('count');
if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
  let n = 0;
  setInterval(() => { n = n >= 30 ? 0 : n + 1; count.textContent = n; }, 330);
} else count.textContent = '30';
const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: .15 });
document.querySelectorAll('.cards article, .flow li, .band, .section h2').forEach(el => { el.classList.add('reveal'); io.observe(el); });
