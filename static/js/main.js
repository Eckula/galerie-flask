// static/js/main.js — v3 (météo sans popup + horloge + burger)
// ➜ Localisation par IP (pas d’autorisation nécessaire). On conserve la géoloc navigateur en option.

const USE_BROWSER_GEO = false; // passe à true si tu veux déclencher la popup et une précision GPS

// Burger
const burger = document.getElementById('burger');
const drawer = document.getElementById('drawer');
const closeDrawer = document.getElementById('closeDrawer');
if (burger && drawer) {
  const open = () => { drawer.setAttribute('aria-hidden','false'); burger.setAttribute('aria-expanded','true'); };
  const close = () => { drawer.setAttribute('aria-hidden','true'); burger.setAttribute('aria-expanded','false'); };
  burger.addEventListener('click', open);
  closeDrawer?.addEventListener('click', close);
  drawer.addEventListener('click', (e)=>{ if(e.target === drawer) close(); });
  window.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') close(); });
}

// Horloge
const clockEl = document.getElementById('clock');
if (clockEl) {
  const tick = () => {
    const d = new Date(); const hh = String(d.getHours()).padStart(2,'0'); const mm = String(d.getMinutes()).padStart(2,'0');
    clockEl.textContent = `${hh}:${mm}`;
  };
  tick(); setInterval(tick, 30 * 1000);
}

// Météo
const weatherEl = document.getElementById('weather');
async function showWeather(lat, lon, cityHint=''){
  try{
    const w = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`).then(r=>r.json());
    const t = Math.round(w?.current_weather?.temperature ?? 0);
    let city = cityHint;
    if(!city){
      try {
        const rev = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`).then(r=>r.json());
        city = rev?.address?.city || rev?.address?.town || rev?.address?.village || rev?.address?.municipality || '';
      } catch {}
    }
    weatherEl.textContent = `${t}°${city ? '  ' + city : ''}`;
  }catch{ weatherEl.textContent = '—°'; }
}
async function locateByIP(){
  try{
    const info = await fetch('https://ipapi.co/json/').then(r=>r.json());
    const [lat, lon] = [info.latitude, info.longitude];
    const city = info.city || '';
    if(lat && lon) { showWeather(lat, lon, city); return; }
    showWeather(45.75, 4.85); // fallback Lyon
  }catch{ showWeather(45.75, 4.85); }
}

if (weatherEl) {
  if (USE_BROWSER_GEO && navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos)=> showWeather(pos.coords.latitude, pos.coords.longitude),
      ()=> locateByIP()
    );
  } else {
    locateByIP(); // pas de popup
  }
}
