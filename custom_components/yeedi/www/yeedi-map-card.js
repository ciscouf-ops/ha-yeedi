/*
 * yeedi map card — served by the yeedi integration, nothing else to install.
 *
 *   type: custom:yeedi-map-card
 *   entity: vacuum.yeedi_vac_max
 *   title: Vacuum            # optional
 *   room_names:              # optional, room id -> name
 *     2: Living room
 *   controls: true           # optional, buttons and settings under the map
 *
 * Draws the rooms reported by the robot, the dock, the robot and the trace of the
 * current cleaning. Tap rooms to choose them (the numbers give the order), then
 * "Clean". The data comes live from the integration (WebSocket "yeedi/map/subscribe").
 */

const CARD_VERSION = '0.2.8';

const TEXT = {
  en: {
    clean: 'Clean', clean_all: 'Clean everything', clean_rooms: (n) => `Clean ${n} room${n > 1 ? 's' : ''}`, pause: 'Pause',
    resume: 'Resume', dock: 'Dock', clear: 'Clear', last_clean: 'Last cleaning', zone: 'Zone', clean_zone: 'Clean the zone', zone_help: 'Draw a rectangle on the map.', no_map: 'Waiting for the map…',
    no_outline: 'The robot did not send the outline of the rooms: choose them below.',
    not_yeedi: 'This entity is not a yeedi vacuum.', fan: 'Suction', water: 'Water', mop_only_short: 'Off',
    states: { cleaning: 'Cleaning', returning: 'Returning to the dock', docked: 'Docked',
      idle: 'Idle', paused: 'Paused', error: 'Error' },
    since: 'started at', end_at: 'ends around', left: (n) => `~${n} min left`,
  },
  fr: {
    clean: 'Nettoyer', clean_all: 'Nettoyer tout', clean_rooms: (n) => `Nettoyer ${n} pièce${n > 1 ? 's' : ''}`, pause: 'Pause',
    resume: 'Reprendre', dock: 'Base', clear: 'Effacer', last_clean: 'Dernier nettoyage', zone: 'Zone', clean_zone: 'Nettoyer la zone', zone_help: 'Trace un rectangle sur le plan.', no_map: 'En attente de la carte…',
    no_outline: "Le robot n'a pas envoyé le contour des pièces : choisis-les ci-dessous.",
    not_yeedi: "Cette entité n'est pas un aspirateur yeedi.", fan: 'Aspiration', water: 'Eau', mop_only_short: 'Coupée',
    states: { cleaning: 'Nettoyage', returning: 'Retour à la base', docked: 'Sur la base',
      idle: 'À l’arrêt', paused: 'En pause', error: 'Erreur' },
    since: 'commencé à', end_at: 'fin vers', left: (n) => `reste ~${n} min`,
  },
  de: {
    clean: 'Reinigen', clean_all: 'Alles reinigen', clean_rooms: (n) => `${n} ${n > 1 ? 'Räume' : 'Raum'} reinigen`, pause: 'Pause',
    resume: 'Fortsetzen', dock: 'Station', clear: 'Zurücksetzen', last_clean: 'Letzte Reinigung', zone: 'Zone', clean_zone: 'Zone reinigen', zone_help: 'Ziehe ein Rechteck auf der Karte.', no_map: 'Warte auf die Karte…',
    no_outline: 'Der Roboter hat keine Raumumrisse gesendet: wähle die Räume unten aus.',
    not_yeedi: 'Diese Entität ist kein yeedi-Staubsauger.', fan: 'Saugkraft', water: 'Wasser', mop_only_short: 'Aus',
    states: { cleaning: 'Reinigt', returning: 'Rückkehr zur Station', docked: 'An der Station',
      idle: 'Bereit', paused: 'Pausiert', error: 'Fehler' },
    since: 'gestartet um', end_at: 'Ende gegen', left: (n) => `noch ~${n} Min.`,
  },
  es: {
    clean: 'Limpiar', clean_all: 'Limpiar todo', clean_rooms: (n) => `Limpiar ${n} habitaci${n > 1 ? 'ones' : 'ón'}`, pause: 'Pausa',
    resume: 'Reanudar', dock: 'Base', clear: 'Borrar', last_clean: 'Última limpieza', zone: 'Zona', clean_zone: 'Limpiar la zona', zone_help: 'Dibuja un rectángulo en el mapa.', no_map: 'Esperando el mapa…',
    no_outline: 'El robot no envió el contorno de las habitaciones: elígelas abajo.',
    not_yeedi: 'Esta entidad no es una aspiradora yeedi.', fan: 'Succión', water: 'Agua', mop_only_short: 'Apagada',
    states: { cleaning: 'Limpiando', returning: 'Volviendo a la base', docked: 'En la base',
      idle: 'Inactiva', paused: 'En pausa', error: 'Error' },
    since: 'iniciada a las', end_at: 'fin hacia las', left: (n) => `quedan ~${n} min`,
  },
  it: {
    clean: 'Pulisci', clean_all: 'Pulisci tutto', clean_rooms: (n) => `Pulisci ${n} stanz${n > 1 ? 'e' : 'a'}`, pause: 'Pausa',
    resume: 'Riprendi', dock: 'Base', clear: 'Annulla', last_clean: 'Ultima pulizia', zone: 'Zona', clean_zone: 'Pulisci la zona', zone_help: 'Disegna un rettangolo sulla mappa.', no_map: 'In attesa della mappa…',
    no_outline: 'Il robot non ha inviato il contorno delle stanze: scegline qui sotto.',
    not_yeedi: 'Questa entità non è un aspirapolvere yeedi.', fan: 'Aspirazione', water: 'Acqua', mop_only_short: 'Spenta',
    states: { cleaning: 'Pulizia', returning: 'Ritorno alla base', docked: 'Alla base',
      idle: 'Inattivo', paused: 'In pausa', error: 'Errore' },
    since: 'iniziata alle', end_at: 'fine verso le', left: (n) => `mancano ~${n} min`,
  },
};

// Generic room names sent by the robot (deebot-client), translated.
const ROOM_NAMES = {
  fr: { 'Default': 'Pièce', 'Living Room': 'Séjour', 'Dining Room': 'Salle à manger',
    'Bedroom': 'Chambre', 'Study': 'Bureau', 'Kitchen': 'Cuisine', 'Bathroom': 'Salle de bain',
    'Laundry': 'Buanderie', 'Lounge': 'Salon', 'Storeroom': 'Débarras',
    'Kids room': 'Chambre d’enfant', 'Sunroom': 'Véranda', 'Corridor': 'Couloir',
    'Balcony': 'Balcon', 'Gym': 'Salle de sport' },
  de: { 'Default': 'Raum', 'Living Room': 'Wohnzimmer', 'Dining Room': 'Esszimmer', 'Bedroom': 'Schlafzimmer',
    'Study': 'Arbeitszimmer', 'Kitchen': 'Küche', 'Bathroom': 'Bad', 'Laundry': 'Waschküche', 'Lounge': 'Salon',
    'Storeroom': 'Abstellraum', 'Kids room': 'Kinderzimmer', 'Sunroom': 'Wintergarten', 'Corridor': 'Flur',
    'Balcony': 'Balkon', 'Gym': 'Fitnessraum' },
  es: { 'Default': 'Habitación', 'Living Room': 'Salón', 'Dining Room': 'Comedor', 'Bedroom': 'Dormitorio',
    'Study': 'Despacho', 'Kitchen': 'Cocina', 'Bathroom': 'Baño', 'Laundry': 'Lavadero', 'Lounge': 'Sala de estar',
    'Storeroom': 'Trastero', 'Kids room': 'Cuarto infantil', 'Sunroom': 'Galería', 'Corridor': 'Pasillo',
    'Balcony': 'Balcón', 'Gym': 'Gimnasio' },
  it: { 'Default': 'Stanza', 'Living Room': 'Soggiorno', 'Dining Room': 'Sala da pranzo', 'Bedroom': 'Camera da letto',
    'Study': 'Studio', 'Kitchen': 'Cucina', 'Bathroom': 'Bagno', 'Laundry': 'Lavanderia', 'Lounge': 'Salotto',
    'Storeroom': 'Ripostiglio', 'Kids room': 'Cameretta', 'Sunroom': 'Veranda', 'Corridor': 'Corridoio',
    'Balcony': 'Balcone', 'Gym': 'Palestra' },
};

// Icons for the suction and water levels (fallbacks by position: _0, _1, …).
const FAN_ICONS = { mop_only: 'mdi:fan-off', quiet: 'mdi:fan-minus', normal: 'mdi:fan-speed-1', max: 'mdi:fan-speed-2', max_plus: 'mdi:fan-speed-3',
  _0: 'mdi:fan-speed-1', _1: 'mdi:fan-speed-2', _2: 'mdi:fan-speed-3', _3: 'mdi:fan-plus' };
const WATER_ICONS = { low: 'mdi:water-minus', medium: 'mdi:water', high: 'mdi:water-plus', ultrahigh: 'mdi:waves',
  _0: 'mdi:water-minus', _1: 'mdi:water', _2: 'mdi:water-plus', _3: 'mdi:waves' };

// Even-odd test of a point against a polygon given as [[x, y], ...].
function pointInPolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

const MIN_ZONE_MM = 1000; // smallest side of a zone sent to the robot
const PALETTE = ['#4f8edc', '#e0a04a', '#5bb07a', '#c46fb8', '#d96a5c', '#4fb3bf', '#9a8bd6', '#b5a046'];

class YeediMapCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement('yeedi-map-card-editor');
  }

  static getStubConfig(hass) {
    const entity = Object.values(hass.entities || {}).find(
      (e) => e.platform === 'yeedi' && e.entity_id.startsWith('vacuum.'),
    );
    return { entity: entity ? entity.entity_id : '', controls: true };
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error('entity is required');
    const changed = !this._config || this._config.entity !== config.entity;
    this._config = { controls: true, ...config };
    this._selected = [];
    this._zoneMode = false; // drawing a rectangle to clean instead of picking rooms
    this._zone = null; // {x1, y1, x2, y2} in robot coordinates (mm)
    this._drag = null;
    if (changed) this._unsubscribe();
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first || !this._unsub) this._subscribe();
    const st = hass.states[this._config.entity];
    const key = st ? `${st.state}|${st.last_updated}|${this._otherStates()}` : '';
    if (key !== this._key) { this._key = key; this._render(); }
  }

  getCardSize() { return 6; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: 'auto' }; }

  connectedCallback() { if (this._hass && !this._unsub) this._subscribe(); }
  disconnectedCallback() { this._unsubscribe(); }

  // ---------------------------------------------------------------- data

  async _subscribe() {
    if (!this._hass || !this._config || this._subscribing) return;
    this._subscribing = true;
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (data) => { this._data = data; this._error = null; if (!this._patch()) this._render(); },
        { type: 'yeedi/map/subscribe', entity_id: this._config.entity },
      );
    } catch (err) {
      this._error = 'not_yeedi';
      this._render();
    } finally {
      this._subscribing = false;
    }
  }

  _unsubscribe() {
    if (this._unsub) { try { this._unsub(); } catch (e) { /* closed */ } }
    this._unsub = null;
    this._data = null;
  }

  // While the robot cleans, a new position arrives every few seconds. When
  // only the robot and its trace changed, move them in place (the robot
  // glides there with a CSS transition) instead of rebuilding the card.
  _patch() {
    const d = this._data, root = this.shadowRoot;
    if (!d || !root || !this._geo || !this._mapKey) return false;
    const svg = root.querySelector('svg.plan');
    const st = this._hass && this._hass.states[this._config.entity];
    if (!svg || !st || st.state !== 'cleaning' || !d.robot) return false;
    const rooms = d.rooms.filter((x) => x.outline && x.outline.length > 2);
    const vb = svg.viewBox.baseVal;
    const X = (x) => x - this._geo.x0, Y = (y) => this._geo.y1 - y;
    const rx = X(d.robot.x), ry = Y(d.robot.y);
    if (rx < 0 || ry < 0 || rx > vb.width || ry > vb.height) return false; // map must grow: full render
    const key = JSON.stringify([d.map_id, rooms.map((r) => [r.id, r.outline]), d.dock, d.no_mop, d.walls, this._geo.x0, this._geo.y1, true, this._zoneMode, this._zone, this._selected, this._active]);
    if (key !== this._mapKey) return false;
    const g = svg.querySelector('.robotg');
    if (!g) return false;
    g.style.transform = `translate(${rx.toFixed(0)}px,${ry.toFixed(0)}px) scale(${this._scale})`;
    const a = ((d.robot.a || 0) * Math.PI) / 180;
    const line = g.querySelector('.heading');
    if (line) { line.setAttribute('x2', (Math.cos(a) * 120).toFixed(0)); line.setAttribute('y2', (-Math.sin(a) * 120).toFixed(0)); }
    if (d.trace && d.trace.length > 1) {
      let band = svg.querySelector('.band');
      if (!band) return false;
      band.setAttribute('d', this._smoothPath(d.trace, X, Y));
    }
    // Footer (room, end time, time left) and progress bar.
    const foot = root.querySelector('.foot');
    if (d.progress) {
      const html = this._progressFoot();
      if (!foot || !html) return false;
      const tmp = document.createElement('div');
      tmp.innerHTML = html;
      const newFoot = tmp.querySelector('.foot'), newBar = tmp.querySelector('.bar');
      const bar = foot.nextElementSibling && foot.nextElementSibling.classList.contains('bar') ? foot.nextElementSibling : null;
      if (newFoot) foot.textContent = newFoot.textContent;
      if (bar && newBar) bar.firstElementChild.style.width = newBar.firstElementChild.style.width;
      else if (!!bar !== !!newBar) return false;
    }
    return true;
  }

  _t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || 'en').split('-')[0];
    return { text: TEXT[lang] || TEXT.en, rooms: ROOM_NAMES[lang] || {} };
  }

  // Entities of the same robot: battery sensor and water flow select.
  _related() {
    const ent = this._hass?.entities?.[this._config.entity];
    if (!ent || !ent.device_id) return {};
    const same = Object.values(this._hass.entities).filter((e) => e.device_id === ent.device_id);
    const battery = same.find((e) => e.entity_id.startsWith('sensor.')
      && this._hass.states[e.entity_id]?.attributes?.device_class === 'battery');
    const water = same.find((e) => e.entity_id.startsWith('select.')
      && (e.translation_key === 'water_amount' || /water/.test(e.entity_id)));
    const suction = same.find((e) => e.entity_id.startsWith('select.') && e.translation_key === 'suction');
    const area = same.find((e) => e.entity_id.startsWith('sensor.') && e.translation_key === 'stats_area');
    const time = same.find((e) => e.entity_id.startsWith('sensor.') && e.translation_key === 'stats_time');
    return { battery: battery?.entity_id, water: water?.entity_id, suction: suction?.entity_id,
      area: area?.entity_id, time: time?.entity_id };
  }

  _otherStates() {
    const r = this._related();
    return [r.battery, r.water, r.suction, r.area, r.time].map((e) => (e ? this._hass.states[e]?.state : '')).join('|');
  }

  // Name of a room: the card's own setting, else the Home Assistant area the room is
  // associated with (vacuum entity settings), else the name reported by the robot.
  _roomName(room) {
    const custom = this._config.room_names || {};
    if (custom[room.id] != null && String(custom[room.id]).trim()) return String(custom[room.id]);
    if (room.area_name) return room.area_name;
    const { rooms } = this._t();
    return rooms[room.robot_name || room.name] || room.robot_name || room.name || `#${room.id}`;
  }

  // ------------------------------------------------------------- actions

  _call(service, data = {}) {
    this._hass.callService('vacuum', service, { entity_id: this._config.entity, ...data });
  }

  // The robot takes a few seconds to report its new state after a command:
  // grey the main button out meanwhile, so it cannot be tapped twice.
  _wait() {
    const st = this._hass.states[this._config.entity];
    clearTimeout(this._pendingTimer);
    this._pending = { state: st ? st.state : null, since: Date.now() };
    this._pendingTimer = setTimeout(() => { this._pending = null; this._render(); }, 15000);
    this._render();
  }

  // What the robot was sent to clean from this card, shown on the map until it is
  // back on the dock (or idle again). Forgotten as soon as the robot is docked.
  _activeJob() {
    if (!this._active) return null;
    const st = this._hass?.states?.[this._config.entity]?.state;
    if ((st === 'docked' || st === 'idle') && !this._isPending()) { this._active = null; return null; }
    return this._active;
  }

  _isPending() {
    if (!this._pending) return false;
    const st = this._hass.states[this._config.entity];
    if (st && st.state !== this._pending.state) { this._pending = null; clearTimeout(this._pendingTimer); return false; }
    return true;
  }

  _cleanSelected() {
    if (this._zone) {
      const z = this._zone;
      const c = [Math.min(z.x1, z.x2), Math.min(z.y1, z.y2), Math.max(z.x1, z.x2), Math.max(z.y1, z.y2)].map((v) => Math.round(v));
      this._call('send_command', { command: 'custom_area', params: { coordinates: c.join(','), cleanings: 1 } });
      // Keep the zone on the map while the robot cleans it (see _activeJob).
      this._active = { zone: z, rooms: [] };
      this._zone = null; this._zoneMode = false;
      this._wait();
      return;
    }
    if (!this._selected.length) { this._call('start'); this._wait(); return; }
    this._call('send_command', {
      command: 'spot_area',
      params: { rooms: this._selected.join(','), cleanings: 1 },
    });
    this._active = { zone: null, rooms: this._selected.slice() };
    this._selected = [];
    this._wait();
  }

  _toggleRoom(id) {
    const i = this._selected.indexOf(id);
    if (i >= 0) this._selected.splice(i, 1); else this._selected.push(id);
    this._render();
  }

  // -------------------------------------------------------------- render

  _render() {
    if (!this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
      this.shadowRoot.addEventListener('click', (ev) => this._onClick(ev));
      this.shadowRoot.addEventListener('pointerdown', (ev) => this._onPointer(ev, 'down'));
      this.shadowRoot.addEventListener('pointermove', (ev) => this._onPointer(ev, 'move'));
      this.shadowRoot.addEventListener('pointerup', (ev) => this._onPointer(ev, 'up'));
      this.shadowRoot.addEventListener('pointercancel', (ev) => this._onPointer(ev, 'up'));
    }
    const { text } = this._t();
    const st = this._hass?.states?.[this._config.entity];
    const title = this._config.title ?? st?.attributes?.friendly_name ?? 'yeedi';
    const moving = ['cleaning', 'returning'].includes(st?.state);
    const r = this._related();
    const battery = r.battery ? this._hass.states[r.battery]?.state : null;
    // Battery with its icon, so the percentage is not read as a cleaning progress.
    let bat = '';
    if (battery && !isNaN(battery)) {
      const pct = Math.max(0, Math.min(100, Math.round(battery))), docked = st?.state === 'docked';
      const charging = docked && pct < 100;
      // Colour: charging = blue, full/ok = green, getting low = orange, needs charging = red.
      const tone = charging ? 'charging' : pct >= 50 ? 'ok' : pct >= 20 ? 'low' : 'empty';
      // A drawn battery: the fill is the level, the percentage sits inside it.
      const w = Math.round(36 * pct / 100);
      const bolt = charging ? '<path class="bolt" d="M35.5 1.5 L31.5 9 H34.5 L33 14.5 L38 7 H35 Z"/>' : '';
      bat = `<svg class="bat ${tone}" viewBox="0 0 44 16" width="44" height="16" aria-label="${pct} %">
        <rect class="shell" x="0.5" y="0.5" width="39" height="15" rx="3"/>
        <rect class="tip" x="40.5" y="5" width="3" height="6" rx="1"/>
        <rect class="fill" x="2" y="2" width="${w}" height="12" rx="2"/>
        <text x="20" y="12">${pct}%</text>${bolt}
      </svg>`;
    }
    const status = [esc(text.states[st?.state] || st?.state || ''), bat].filter(Boolean).join('<span class="sep">·</span>');

    let body;
    if (this._error) body = `<div class="msg">${text[this._error]}</div>`;
    else if (!this._data) body = `<div class="msg">${text.no_map}</div>`;
    else body = this._map(moving);

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="head">
          <div class="title">${esc(title)}</div>
          <div class="status">${status}</div>
        </div>
        ${body}
        ${this._config.controls !== false && st ? this._controls(st, r, moving) : ''}
      </ha-card>`;
  }

  // The robot reports room outlines as coarse staircases. Steps shorter than
  // TOL are absorbed into the neighbouring edge, keeping every angle straight.
  _roomPath(outline, X, Y) {
    let p = outline.map(([x, y]) => [X(x), Y(y)]);
    if (p.length > 2 && p[0][0] === p[p.length - 1][0] && p[0][1] === p[p.length - 1][1]) p = p.slice(0, -1);
    const TOL = 220;
    const len = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
    const dedupe = () => {
      // Drop repeated points and points on a straight line.
      for (let k = 0; k < p.length && p.length > 3; k++) {
        const a = p[(k + p.length - 1) % p.length], b = p[k], c = p[(k + 1) % p.length];
        const cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
        if (len(a, b) < 1 || Math.abs(cross) < 1) { p.splice(k, 1); k = -1; }
      }
    };
    dedupe();
    for (let pass = 0; pass < 20 && p.length > 4; pass++) {
      // Shortest edge below TOL whose neighbours are parallel (a step).
      let best = -1, bl = TOL;
      for (let k = 0; k < p.length; k++) {
        const a = p[(k + p.length - 1) % p.length], b = p[k], c = p[(k + 1) % p.length], d = p[(k + 2) % p.length];
        const l = len(b, c);
        if (l >= bl) continue;
        const v1 = [b[0] - a[0], b[1] - a[1]], v2 = [d[0] - c[0], d[1] - c[1]];
        if (v1[0] * v2[0] + v1[1] * v2[1] > 0) { best = k; bl = l; }
      }
      if (best < 0) break;
      const n = p.length, ia = (best + n - 1) % n, ib = best, ic = (best + 1) % n, id = (best + 2) % n;
      // Move the shorter neighbour onto the line of the longer one.
      const la = len(p[ia], p[ib]), lc = len(p[ic], p[id]);
      const horiz = Math.abs(p[ib][1] - p[ic][1]) < Math.abs(p[ib][0] - p[ic][0]); // step edge is horizontal → neighbours vertical
      if (la >= lc) {
        if (horiz) { p[ic][0] = p[ib][0]; p[id][0] = p[ib][0]; } else { p[ic][1] = p[ib][1]; p[id][1] = p[ib][1]; }
      } else if (horiz) { p[ib][0] = p[ic][0]; p[ia][0] = p[ic][0]; } else { p[ib][1] = p[ic][1]; p[ia][1] = p[ic][1]; }
      dedupe();
    }
    if (p.length < 3) return '';
    return 'M' + p.map(([x, y]) => `${x.toFixed(0)},${y.toFixed(0)}`).join(' L') + ' Z';
  }

  // Trace of the robot: positions averaged over a short window, then joined
  // with quadratic curves through the midpoints (no overshoot).
  _smoothPath(trace, X, Y) {
    const pts = trace.map(([x, y]) => [X(x), Y(y)]);
    if (pts.length < 2) return '';
    const sm = pts.map((p, i) => {
      if (i === 0 || i === pts.length - 1) return p;
      const a = pts[i - 1], c = pts[i + 1];
      return [(a[0] + 2 * p[0] + c[0]) / 4, (a[1] + 2 * p[1] + c[1]) / 4];
    });
    const f = (v) => v.toFixed(0);
    let d = `M${f(sm[0][0])},${f(sm[0][1])}`;
    for (let i = 1; i < sm.length - 1; i++) {
      const mx = (sm[i][0] + sm[i + 1][0]) / 2, my = (sm[i][1] + sm[i + 1][1]) / 2;
      d += ` Q${f(sm[i][0])},${f(sm[i][1])} ${f(mx)},${f(my)}`;
    }
    const l = sm[sm.length - 1];
    return d + ` L${f(l[0])},${f(l[1])}`;
  }

  // Room label: shrink to fit the room, split on a space when needed.
  _roomLabel(label, widthMm, u) {
    const fit = (txt, size) => txt.length * size * 0.56 <= widthMm * 0.92;
    const max = u * 2.5, min = u * 1.5;
    let lines = [label], font = max;
    const need = (ls) => Math.max(...ls.map((l) => l.length)) * 0.56;
    font = Math.min(max, (widthMm * 0.92) / need(lines));
    if (font < max * 0.8 && label.includes(' ')) {
      const words = label.split(' ');
      let best = null;
      for (let k = 1; k < words.length; k++) {
        const cand = [words.slice(0, k).join(' '), words.slice(k).join(' ')];
        if (!best || need(cand) < need(best)) best = cand;
      }
      lines = best;
      font = Math.min(max, (widthMm * 0.92) / need(lines));
    }
    font = Math.max(min, Math.round(font));
    return { lines, font, fits: fit(lines[0], font) && fit(lines[lines.length - 1], font) };
  }

  _map(moving) {
    const { text } = this._t();
    const d = this._data;
    const rooms = d.rooms.filter((x) => x.outline && x.outline.length > 2);
    const pts = [];
    rooms.forEach((x) => pts.push(...x.outline));
    // Dock and robot extend the drawing, unless a bogus position would squash the rooms.
    const near = (p) => {
      if (!pts.length) return true;
      const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]), R = 3000;
      return p[0] > Math.min(...xs) - R && p[0] < Math.max(...xs) + R && p[1] > Math.min(...ys) - R && p[1] < Math.max(...ys) + R;
    };
    if (d.dock && near([d.dock.x, d.dock.y])) pts.push([d.dock.x, d.dock.y]);
    if (d.robot && near([d.robot.x, d.robot.y])) pts.push([d.robot.x, d.robot.y]);
    if (!rooms.length) (d.trace || []).forEach((p) => pts.push(p));

    let svg = '';
    if (pts.length) {
      const M = 400;
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const x0 = Math.min(...xs) - M, x1 = Math.max(...xs) + M;
      const y0 = Math.min(...ys) - M, y1 = Math.max(...ys) + M;
      const W = Math.max(x1 - x0, 1000), H = Math.max(y1 - y0, 1000);
      const X = (x) => (x - x0), Y = (y) => (y1 - y); // robot y goes up, SVG y goes down
      const P = (list) => list.map(([x, y]) => `${X(x).toFixed(0)},${Y(y).toFixed(0)}`).join(' ');
      const u = Math.max(W, H) / 100; // drawing unit: 1 % of the map
      const font = Math.round(u * 2.5);
      const choose = !moving;
      const paths = {};
      const job = this._activeJob();
      rooms.forEach((room) => { paths[room.id] = this._roomPath(room.outline, X, Y); });
      const hasSel = choose && this._selected.length > 0;
      this._geo = { x0, y1 }; // to turn pointer positions back into robot coordinates
      const zoning = choose && this._zoneMode;
      let s = `<svg viewBox="0 0 ${W.toFixed(0)} ${H.toFixed(0)}" preserveAspectRatio="xMidYMid meet" class="plan${hasSel ? ' has-sel' : ''}${zoning ? ' zoning' : ''}">`;
      rooms.forEach((room, i) => {
        const sel = this._selected.indexOf(room.id);
        s += `<path class="room${choose ? ' pick' : ''}${sel >= 0 ? ' sel' : ''}" data-room="${room.id}"
          d="${paths[room.id]}" style="--c:${PALETTE[i % PALETTE.length]}"/>`;
      });
      // Selected rooms get a coloured outline on top of the others.
      if (hasSel || (job && job.rooms.length)) rooms.forEach((room) => {
        if (this._selected.includes(room.id) || (job && job.rooms.includes(room.id))) s += `<path class="selring" data-room="${room.id}" d="${paths[room.id]}"/>`;
      });
      if (moving && d.trace && d.trace.length > 1) {
        if (rooms.length) s += `<clipPath id="inside">${rooms.map((x) => `<path d="${paths[x.id]}"/>`).join('')}</clipPath>`;
        const clip = rooms.length ? ' clip-path="url(#inside)"' : '';
        // One band as wide as the robot, on a lightly smoothed path: a single
        // stroke keeps the same opacity where strips overlap.
        s += `<path class="band" d="${this._smoothPath(d.trace, X, Y)}"${clip}/>`;
      }
      // Restrictions set in the yeedi app: no-mop zones (hatched) and virtual walls (red).
      if ((d.no_mop && d.no_mop.length) || (d.walls && d.walls.length)) {
        s += `<defs><pattern id="hatch" width="${(u * 1.2).toFixed(0)}" height="${(u * 1.2).toFixed(0)}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="${(u * 1.2).toFixed(0)}" class="hatchline"/></pattern></defs>`;
        (d.no_mop || []).forEach((z) => { if (z.points.length > 1) s += `<polygon class="nomop" points="${P(z.points)}"/>`; });
        (d.walls || []).forEach((w) => { if (w.points.length > 1) s += `<polyline class="wall" points="${P(w.points)}"/>`; });
      }
      const shownZone = this._zone || (job && job.zone);
      if (shownZone) {
        const z = shownZone;
        const zx = X(Math.min(z.x1, z.x2)), zy = Y(Math.max(z.y1, z.y2));
        s += `<rect class="zone${this._zone ? '' : ' active'}" x="${zx.toFixed(0)}" y="${zy.toFixed(0)}" width="${Math.abs(z.x2 - z.x1).toFixed(0)}" height="${Math.abs(z.y2 - z.y1).toFixed(0)}"/>`;
      }
      rooms.forEach((room) => {
        const rx = room.outline.map((p) => p[0]), ry = room.outline.map((p) => p[1]);
        const cx = X((Math.min(...rx) + Math.max(...rx)) / 2), cy = Y((Math.min(...ry) + Math.max(...ry)) / 2);
        const sel = this._selected.indexOf(room.id);
        const lab = this._roomLabel(this._roomName(room), Math.max(...rx) - Math.min(...rx), u);
        const lh = lab.font * 1.15, nl = lab.lines.length;
        const block = (y0) => lab.lines.map((l, k) => `<text class="name" x="${cx}" y="${(y0 + (k - (nl - 1) / 2) * lh).toFixed(0)}" font-size="${lab.font}">${esc(l)}</text>`).join('');
        if (sel >= 0) {
          // Order badge above the name.
          const r = font * 0.8, by = cy - font * 0.7 - (nl * lh) / 2;
          s += `<circle class="badge" cx="${cx}" cy="${by}" r="${r}" data-room="${room.id}"/>
            <text class="badgetxt" x="${cx}" y="${by}" font-size="${Math.round(font * 1.05)}" data-room="${room.id}">${sel + 1}</text>` + block(cy + font * 0.5);
        } else {
          s += block(cy);
        }
      });
      if (shownZone) {
        // Surface of the zone, in its middle (on top of the room names).
        const z = shownZone;
        s += `<text class="zonetxt" x="${X((z.x1 + z.x2) / 2).toFixed(0)}" y="${Y((z.y1 + z.y2) / 2).toFixed(0)}" font-size="${Math.round(font * 1.1)}">${this._zoneArea(z)}</text>`;
      }
      if (d.dock) {
        s += `<g transform="translate(${X(d.dock.x)},${Y(d.dock.y)})"><g transform="scale(${(u / 75).toFixed(3)})"><rect x="-190" y="-190" width="380" height="380" rx="90" class="dock"/>
          <path transform="translate(-144,-144) scale(12)" fill="#fff" d="M12 3L2 12h3v8h14v-8h3L12 3z"/></g></g>`;
      }
      // Robot: at its reported position, or on the dock when docked (the robot
      // stops reporting its position once it is charging).
      const docked = st_docked(this) && d.dock;
      const rob = docked ? { ...d.dock, a: (d.robot && d.robot.a) || d.dock.a } : d.robot;
      if (rob) {
        const a = ((rob.a || 0) * Math.PI) / 180;
        const hx = Math.cos(a) * 120, hy = -Math.sin(a) * 120;
        s += `<g class="robotg" style="transform:translate(${X(rob.x).toFixed(0)}px,${Y(rob.y).toFixed(0)}px) scale(${(u / 75).toFixed(3)})">
          ${moving ? '<circle r="320" class="halo"/>' : ''}
          <circle r="170" class="robot"/><line x1="0" y1="0" x2="${hx.toFixed(0)}" y2="${hy.toFixed(0)}" class="heading"/></g>`;
      }
      this._mapKey = JSON.stringify([d.map_id, rooms.map((r) => [r.id, r.outline]), d.dock, d.no_mop, d.walls, x0, y1, moving, this._zoneMode, this._zone, this._selected, this._active]);
      this._scale = (u / 75).toFixed(3);
      s += '</svg>';
      svg = `<div class="map">${s}</div>`;
    }

    // Without outlines, rooms are chosen from a list.
    let list = '';
    if (!rooms.length && d.rooms.length) {
      list = `<div class="msg small">${text.no_outline}</div><div class="chips">${d.rooms.map((room) => {
        const sel = this._selected.indexOf(room.id);
        return `<button class="chip${sel >= 0 ? ' on' : ''}" data-room="${room.id}" ${moving ? 'disabled' : ''}>${sel >= 0 ? `${sel + 1}. ` : ''}${esc(this._roomName(room))}</button>`;
      }).join('')}</div>`;
    }
    if (!svg && !list) return `<div class="msg">${text.no_map}</div>`;
    return svg + list;
  }

  _controls(st, related, moving) {
    const { text } = this._t();
    const paused = st.state === 'paused';
    const n = this._selected.length;
    // One room: name it ("Clean Kitchen"); several: count them.
    let roomsLabel = n ? text.clean_rooms(n) : text.clean_all;
    if (n === 1) {
      const room = (this._data?.rooms || []).find((r) => r.id === this._selected[0]);
      if (room) roomsLabel = `${text.clean} ${esc(this._roomName(room))}`;
    }
    let main;
    const pending = this._isPending();
    // In zone mode, nothing to start until a rectangle is drawn.
    const noZone = this._zoneMode && !this._zone && !moving && !paused;
    const dis = pending || noZone ? ' disabled' : '';
    const icon = (i) => `<ha-icon icon="${pending ? 'mdi:loading' : i}"${pending ? ' class="spin"' : ''}></ha-icon>`;
    if (moving) main = `<button class="btn main" data-act="pause"${dis}>${icon('mdi:pause')}${text.pause}</button>`;
    else if (paused) main = `<button class="btn main" data-act="resume"${dis}>${icon('mdi:play')}${text.resume}</button>`;
    else main = `<button class="btn main" data-act="clean"${dis}>${icon('mdi:play')}${this._zoneMode ? text.clean_zone : roomsLabel}</button>`;
    const clear = (n || this._zone) && !moving ? `<button class="btn flat" data-act="clear">${text.clear}</button>` : '';
    const hasMap = this._data && this._data.rooms && this._data.rooms.some((r) => r.outline && r.outline.length > 2);
    const zone = !moving && !paused && hasMap && !n
      ? `<button class="btn flat${this._zoneMode ? ' on' : ''}" data-act="zone" title="${esc(text.zone_help)}"><ha-icon icon="mdi:selection-drag"></ha-icon>${text.zone}</button>` : '';
    const dock = st.state !== 'docked' ? `<button class="btn flat" data-act="dock"${pending ? ' disabled' : ''}><ha-icon icon="mdi:home-import-outline"></ha-icon>${text.dock}</button>` : '';

    // Suction and water: one icon per level (the label is the tooltip), the current
    // level written next to the row title.
    const sst = related.suction ? this._hass.states[related.suction] : null;
    const fanList = sst ? sst.attributes.options || [] : st.attributes.fan_speed_list || [];
    const fanNow = sst ? sst.state : st.attributes.fan_speed;
    const fanLabel = (f) => {
      if (sst && this._hass.formatEntityState) return this._hass.formatEntityState(sst, f);
      if (this._hass.formatEntityAttributeValue) return this._hass.formatEntityAttributeValue(st, 'fan_speed', f);
      return f;
    };
    // Mop only is a toggle in front of the suction gauge, not a level.
    // It takes the place of the gauge icon: a tap turns the vacuum motor off.
    const mopOn = fanNow === 'mop_only';
    if (fanNow && !mopOn) this._lastFan = fanNow; // to turn the motor back on from the icon
    // A tap on the icon turns the vacuum motor off, or back on at the last level.
    const iconTarget = mopOn ? (this._lastFan || fanList.find((f) => f !== 'mop_only')) : 'mop_only';
    const mopChip = fanList.includes('mop_only')
      ? `<button class="gicon${mopOn ? ' on' : ''}" data-fan="${esc(iconTarget)}" title="${esc(fanLabel('mop_only'))}" aria-label="${esc(fanLabel('mop_only'))}"><ha-icon icon="${mopOn ? 'mdi:fan-off' : 'mdi:fan'}"></ha-icon></button>`
      : '<ha-icon icon="mdi:fan"></ha-icon>';
    // Under the row title, "mop only" is too long: show a short word instead.
    const fanShort = (f) => (f === 'mop_only' ? text.mop_only_short : fanLabel(f));
    const fan = fanList.length
      ? this._levelRow(text.fan, mopChip, fanList.filter((f) => f !== 'mop_only'), fanNow, fanShort, 'data-fan') : '';

    const wst = related.water ? this._hass.states[related.water] : null;
    const waterLabel = (o) => (this._hass.formatEntityState ? this._hass.formatEntityState(wst, o) : o);
    const water = wst && wst.attributes.options
      ? this._levelRow(text.water, '<ha-icon icon="mdi:water-outline"></ha-icon>', wst.attributes.options, wst.state, waterLabel, 'data-water') : '';

    const hint = this._zoneMode && !this._zone ? `<div class="foot">${esc(text.zone_help)}</div>` : '';
    return `<div class="actions">${main}${clear}${zone}${dock}</div>${hint}${fan}${water}${this._lastClean(related, moving)}`;
  }

  // "Last cleaning: 32 min · 18 m² · 2 h ago", from the statistics sensors.
  _lastClean(related, moving) {
    if (moving) return this._progressFoot();
    const { text } = this._t();
    const lang = this._hass?.locale?.language || 'en';
    const parts = [];
    let when = null;
    for (const key of ['time', 'area']) {
      const st = related[key] ? this._hass.states[related[key]] : null;
      if (!st || isNaN(parseFloat(st.state)) || parseFloat(st.state) <= 0) continue;
      let v = parseFloat(st.state), u = st.attributes.unit_of_measurement || '';
      if (key === 'time') {
        if (u === 's') { v = v / 60; u = 'min'; }
        if (u === 'h') { v = v * 60; u = 'min'; }
        v = Math.round(v);
      } else v = Math.round(v * 10) / 10;
      parts.push(`${v.toLocaleString(lang)} ${u}`);
      const t = new Date(st.last_changed).getTime();
      if (!when || t > when) when = t;
    }
    if (!parts.length) return '';
    if (when) {
      const diff = Math.round((when - Date.now()) / 60000);
      const rtf = new Intl.RelativeTimeFormat(lang, { numeric: 'auto' });
      const ago = Math.abs(diff) < 60 ? rtf.format(diff, 'minute')
        : Math.abs(diff) < 60 * 48 ? rtf.format(Math.round(diff / 60), 'hour') : rtf.format(Math.round(diff / 1440), 'day');
      parts.push(ago);
    }
    return `<div class="foot">${esc(text.last_clean)} · ${esc(parts.join(' · '))}</div>`;
  }

  // While cleaning: the room the robot is in, the estimated end and the time left
  // (computed by the integration from the durations learned on previous cleanings).
  _progressFoot() {
    const p = this._data?.progress;
    if (!p) return '';
    const { text } = this._t();
    const lang = this._hass?.locale?.language || 'en';
    const parts = [];
    if (p.room_id != null) {
      const room = (this._data.rooms || []).find((r) => r.id === p.room_id) || { id: p.room_id, name: p.room || '' };
      parts.push(this._roomName(room));
    }
    if (p.end) {
      const hm = new Date(p.end * 1000).toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' });
      parts.push(`${text.end_at} ${hm}`);
    }
    if (p.remaining_minutes != null) parts.push(text.left(p.remaining_minutes));
    if (!parts.length) return '';
    const bar = p.progress != null ? `<div class="bar"><div style="width:${p.progress}%"></div></div>` : '';
    return `<div class="foot">${esc(parts.join(' · '))}</div>${bar}`;
  }

  _levelRow(title, icon, levels, current, labelOf, attr) {
    // A gauge: one segment per level, filled up to the current one.
    const at = levels.indexOf(current);
    const segs = levels.map((o, i) => {
      const label = labelOf(o);
      return `<button class="seg${i <= at ? ' fill' : ''}${i === at ? ' on' : ''}" ${attr}="${esc(o)}" title="${esc(label)}" aria-label="${esc(label)}"></button>`;
    }).join('');
    const now = current != null ? labelOf(current) : '';
    return `<div class="row"><span class="lbl">${esc(title)}<small>${esc(now)}</small></span>
      <div class="chips"><div class="gauge">${icon}${segs}</div></div></div>`;
  }

  _iconRow(title, options, current, labelOf, icons, attr) {
    const chips = options.map((o, i) => {
      const label = labelOf(o);
      const icon = icons[o] || icons[`_${i}`] || 'mdi:circle-small';
      return `<button class="chip icon${current === o ? ' on' : ''}" ${attr}="${esc(o)}" title="${esc(label)}" aria-label="${esc(label)}"><ha-icon icon="${icon}"></ha-icon></button>`;
    }).join('');
    const now = current != null ? labelOf(current) : '';
    return `<div class="row"><span class="lbl">${esc(title)}<small>${esc(now)}</small></span><div class="chips">${chips}</div></div>`;
  }

  // Zone mode: drag on the map to draw the rectangle to clean.
  _onPointer(ev, phase) {
    if (!this._zoneMode || !this._geo) return;
    const svg = ev.composedPath().find((n) => n.tagName === 'svg' && n.classList && n.classList.contains('plan'));
    if (phase === 'down') {
      if (!svg) return;
      const p = this._toRobot(svg, ev);
      this._drag = { x: p.x, y: p.y };
      this._zone = null;
      ev.preventDefault();
      return;
    }
    if (!this._drag) return;
    // The map is re-rendered while dragging: always measure against the current one.
    const current = this.shadowRoot.querySelector('svg.plan');
    if (!current) return;
    const p = this._toRobot(current, ev);
    this._zone = { x1: this._drag.x, y1: this._drag.y, x2: p.x, y2: p.y };
    if (phase === 'up') {
      this._drag = null;
      // Too small to be a zone: treat it as a tap.
      if (Math.abs(this._zone.x2 - this._zone.x1) < 300 || Math.abs(this._zone.y2 - this._zone.y1) < 300) this._zone = null;
      // The robot cleans a zone in ~30 cm strips: a thin rectangle is done in one straight
      // line. Like the yeedi app, widen each side to at least 1 m, around what was drawn.
      else this._zone = this._minZone(this._zone, MIN_ZONE_MM);
    }
    this._render();
  }

  // Floor surface of the drawn zone, e.g. "8 m²": only the part of the rectangle that
  // lies inside a room counts (the robot cannot clean outside the map). Sampled on a
  // 10 cm grid; cached until the zone or the map changes.
  _zoneArea(z) {
    const rooms = ((this._data && this._data.rooms) || []).filter((x) => x.outline && x.outline.length > 2);
    const key = JSON.stringify([z, rooms.map((r) => r.outline)]);
    if (this._areaKey !== key) {
      const x0 = Math.min(z.x1, z.x2), x1 = Math.max(z.x1, z.x2), y0 = Math.min(z.y1, z.y2), y1 = Math.max(z.y1, z.y2);
      const STEP = 100;
      let cells = 0;
      for (let x = x0 + STEP / 2; x < x1; x += STEP) {
        for (let y = y0 + STEP / 2; y < y1; y += STEP) {
          if (rooms.some((r) => pointInPolygon(x, y, r.outline))) cells++;
        }
      }
      const m2 = (cells * STEP * STEP) / 1e6;
      this._areaKey = key;
      this._areaTxt = `${m2 < 10 ? m2.toFixed(1).replace('.0', '') : Math.round(m2)} m²`;
    }
    return this._areaTxt;
  }

  _minZone(z, min) {
    const grow = (a, b) => {
      const lo = Math.min(a, b), hi = Math.max(a, b);
      if (hi - lo >= min) return [lo, hi];
      const mid = (lo + hi) / 2;
      return [mid - min / 2, mid + min / 2];
    };
    const [x1, x2] = grow(z.x1, z.x2), [y1, y2] = grow(z.y1, z.y2);
    return { x1, y1, x2, y2 };
  }

  _toRobot(svg, ev) {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    const m = svg.getScreenCTM();
    const q = m ? pt.matrixTransform(m.inverse()) : pt;
    return { x: q.x + this._geo.x0, y: this._geo.y1 - q.y };
  }

  _onClick(ev) {
    const path = ev.composedPath();
    const el = path.find((n) => n.dataset && (n.dataset.room || n.dataset.act || n.dataset.fan || n.dataset.water));
    if (!el || el.disabled) return;
    const st = this._hass.states[this._config.entity];
    if (el.dataset.room) {
      if (['cleaning', 'returning'].includes(st?.state) || this._zoneMode) return;
      this._toggleRoom(Number(el.dataset.room));
    } else if (el.dataset.act === 'clean') this._cleanSelected();
    else if (el.dataset.act === 'pause') { this._call('pause'); this._wait(); }
    else if (el.dataset.act === 'resume') { this._call('start'); this._wait(); }
    else if (el.dataset.act === 'dock') { this._call('return_to_base'); this._wait(); }
    else if (el.dataset.act === 'clear') { this._selected = []; this._zone = null; this._render(); }
    else if (el.dataset.act === 'zone') { this._zoneMode = !this._zoneMode; if (!this._zoneMode) this._zone = null; this._render(); }
    else if (el.dataset.fan) {
      const sel = this._related().suction;
      if (sel) this._hass.callService('select', 'select_option', { entity_id: sel, option: el.dataset.fan });
      else this._call('set_fan_speed', { fan_speed: el.dataset.fan });
    }
    else if (el.dataset.water) {
      this._hass.callService('select', 'select_option', { entity_id: this._related().water, option: el.dataset.water });
    }
  }
}

function st_docked(card) {
  return card._hass?.states?.[card._config.entity]?.state === 'docked';
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const STYLE = `
  ha-card { overflow: hidden; }
  .head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 14px 16px 6px; }
  .title { font-size: 16px; font-weight: 500; color: var(--primary-text-color); }
  .status { display: inline-flex; align-items: center; gap: 5px; font-size: 13px; color: var(--secondary-text-color); white-space: nowrap; }
  .status .bat { display: inline-block; vertical-align: middle; overflow: visible; }
  .status .bat .shell { fill: none; stroke: var(--secondary-text-color); stroke-opacity: 0.6; }
  .status .bat .tip { fill: var(--secondary-text-color); fill-opacity: 0.6; }
  .status .bat .fill { fill: var(--bat-color); opacity: 0.9; }
  .status .bat text { font: 700 9.5px/1 var(--paper-font-body1_-_font-family, sans-serif); text-anchor: middle;
    fill: var(--primary-text-color); paint-order: stroke; stroke: var(--ha-card-background, var(--card-background-color, #fff)); stroke-width: 1.6px; stroke-linejoin: round; }
  .status .bat .bolt { fill: var(--primary-text-color); paint-order: stroke; stroke: var(--ha-card-background, var(--card-background-color, #fff)); stroke-width: 1.5px; stroke-linejoin: round; }
  .status .bat.ok { --bat-color: var(--success-color, #43a047); }
  .status .bat.charging { --bat-color: var(--primary-color); }
  .status .bat.low { --bat-color: var(--warning-color, #ffa600); }
  .status .bat.empty { --bat-color: var(--error-color, #db4437); }
  .map { padding: 4px 12px; }
  svg { width: 100%; max-width: 560px; height: auto; max-height: 420px; display: block; margin: 0 auto; }
  .room { fill: var(--c); fill-opacity: .28; stroke: var(--card-background-color, #fff); stroke-width: 40; stroke-linejoin: round; transition: fill-opacity .2s; }
  .room.pick { cursor: pointer; }
  .room.pick:hover { fill-opacity: .4; }
  .room.sel { fill-opacity: .62; }
  .has-sel .room:not(.sel) { fill-opacity: .12; }
  .selring { fill: none; stroke: var(--primary-color); stroke-width: 55; stroke-linejoin: round; pointer-events: none; }
  .badge { fill: var(--primary-color); stroke: var(--card-background-color, #fff); stroke-width: 25; }
  .zonetxt { fill: var(--primary-color); font-weight: 600; text-anchor: middle; dominant-baseline: central; pointer-events: none; paint-order: stroke; stroke: var(--card-background-color, #fff); stroke-width: 60; stroke-linejoin: round; }
  .badgetxt { fill: #fff; font-weight: 700; text-anchor: middle; dominant-baseline: central; pointer-events: none; }
  .name { text-anchor: middle; dominant-baseline: middle; fill: var(--primary-text-color); font-weight: 500;
          paint-order: stroke; stroke: var(--card-background-color, #fff); stroke-width: 40; stroke-linejoin: round; pointer-events: none; }
  .band { fill: none; stroke: var(--primary-color); stroke-opacity: .28; stroke-width: 330; stroke-linecap: round; stroke-linejoin: round; }
  .dock { fill: #43a047; stroke: #fff; stroke-width: 35; }
  .robotg { transition: transform 2.5s linear; }
  .robot { fill: var(--primary-color); stroke: #fff; stroke-width: 40; }
  .heading { stroke: #fff; stroke-width: 40; stroke-linecap: round; }
  .halo { fill: var(--primary-color); opacity: .18; animation: pulse 2s ease-in-out infinite; }
  .hatchline { stroke: var(--error-color, #db4437); stroke-width: 18; stroke-opacity: .55; }
  .nomop { fill: url(#hatch); stroke: var(--error-color, #db4437); stroke-width: 20; stroke-opacity: .7; pointer-events: none; }
  .wall { fill: none; stroke: var(--error-color, #db4437); stroke-width: 60; stroke-linecap: round; pointer-events: none; }
  .zone { fill: var(--primary-color); fill-opacity: .22; stroke: var(--primary-color); stroke-width: 40; stroke-dasharray: 90 60; pointer-events: none; }
  .zone.active { fill-opacity: .16; stroke-dasharray: none; stroke-width: 55; }
  svg.zoning { cursor: crosshair; touch-action: none; }
  svg.zoning .room { cursor: crosshair; }
  @keyframes pulse { 50% { opacity: .05; } }
  .msg { padding: 24px 16px; text-align: center; color: var(--secondary-text-color); font-size: 13px; }
  .msg.small { padding: 8px 16px 4px; }
  .actions { display: flex; gap: 8px; padding: 10px 16px 6px; }
  .btn.main { flex: 1 1 auto; justify-content: center; }
  .btn:disabled { opacity: .55; cursor: default; }
  .spin { animation: yeedi-spin 1s linear infinite; }
  @keyframes yeedi-spin { to { transform: rotate(360deg); } }
  .btn { display: inline-flex; align-items: center; gap: 6px; border: none; border-radius: 18px; padding: 8px 16px;
         font: 500 14px var(--paper-font-body1_-_font-family, inherit); cursor: pointer;
         background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .btn.flat { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); color: var(--primary-text-color); }
  .btn.flat.on { background: color-mix(in srgb, var(--primary-color) 22%, transparent); color: var(--primary-color); }
  .btn ha-icon { --mdc-icon-size: 18px; }
  .row { display: flex; align-items: center; gap: 10px; padding: 4px 16px; }
  .row:last-child { padding-bottom: 14px; }
  .foot { padding: 2px 16px 12px; font-size: 12px; color: var(--secondary-text-color); }
  .bar { height: 3px; margin: -8px 16px 12px; border-radius: 2px; background: color-mix(in srgb, var(--primary-color) 18%, transparent); overflow: hidden; }
  .bar > div { height: 100%; border-radius: 2px; background: var(--primary-color); transition: width 1s linear; }
  .row:last-child + .foot { margin-top: -8px; }
  .lbl { font-size: 12px; color: var(--secondary-text-color); min-width: 84px; flex: 0 0 auto; display: flex; flex-direction: column; line-height: 1.2; }
  .lbl small { font-size: 12px; color: var(--primary-text-color); font-weight: 500; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; padding: 2px 0; }
  .row .chips { flex: 1 1 auto; flex-wrap: nowrap; align-items: center; }
  .row .chips::-webkit-scrollbar { display: none; }
  .row .chip { white-space: nowrap; flex: 0 0 auto; }
  .msg + .chips { padding: 4px 16px 8px; }
  .chip { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--divider-color); border-radius: 14px;
          padding: 4px 11px; font-size: 12px; cursor: pointer; background: none; color: var(--primary-text-color); }
  .chip.on { background: color-mix(in srgb, var(--primary-color) 18%, transparent); border-color: var(--primary-color); }
  .chip:disabled { opacity: .5; cursor: default; }
  .chip ha-icon { --mdc-icon-size: 14px; }
  .chip.icon { padding: 5px 9px; border-radius: 16px; }
  .chip.icon ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); }
  .chip.icon.on ha-icon { color: var(--primary-color); }
  .gauge { flex: 1 1 auto; display: flex; align-items: center; gap: 3px; padding: 4px 10px; border: 1px solid var(--divider-color); border-radius: 16px; box-sizing: border-box; height: 32px; }
  .gicon { border: 0; background: none; padding: 0; margin: 0; cursor: pointer; display: inline-flex; align-items: center; }
  .gicon.on ha-icon { color: var(--primary-color); }
  .gauge ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); margin-right: 6px; }
  .seg { flex: 1 1 0; height: 12px; border: 0; padding: 0; margin: 0; cursor: pointer; border-radius: 3px;
         background: color-mix(in srgb, var(--primary-text-color) 12%, transparent); transition: background .15s; }
  .seg:first-of-type { border-radius: 6px 3px 3px 6px; }
  .seg:last-of-type { border-radius: 3px 6px 6px 3px; }
  .seg.fill { background: color-mix(in srgb, var(--primary-color) 55%, transparent); }
  .seg.on { background: var(--primary-color); }
`;


// ------------------------------------------------------------------ editor

const EDITOR_TEXT = {
  en: { title: 'Title', controls: 'Buttons and settings under the map', rooms: 'Rename rooms on this card only (optional)',
    rooms_help: 'Normally leave these empty: the card shows the Home Assistant area each room is associated with (vacuum entity settings → Clean rooms), or else the name from the robot. Type a name here only to override it on this card.', waiting: 'Waiting for the robot’s rooms…' },
  fr: { title: 'Titre', controls: 'Boutons et réglages sous le plan', rooms: 'Renommer les pièces sur cette carte seulement (facultatif)',
    rooms_help: 'À laisser vide en général : la carte affiche la pièce Home Assistant associée (paramètres de l’entité aspirateur → Nettoyer des pièces), sinon le nom donné par le robot. Ne saisir un nom ici que pour le remplacer sur cette carte.', waiting: 'En attente des pièces du robot…' },
  de: { title: 'Titel', controls: 'Tasten und Einstellungen unter der Karte', rooms: 'Räume nur auf dieser Karte umbenennen (optional)',
    rooms_help: 'Normalerweise leer lassen: die Karte zeigt den zugeordneten Home-Assistant-Bereich (Einstellungen der Staubsauger-Entität → Räume reinigen), sonst den Namen vom Roboter. Nur ausfüllen, um ihn auf dieser Karte zu ersetzen.', waiting: 'Warte auf die Räume des Roboters…' },
  es: { title: 'Título', controls: 'Botones y ajustes bajo el mapa', rooms: 'Renombrar habitaciones solo en esta tarjeta (opcional)',
    rooms_help: 'Normalmente déjalo vacío: la tarjeta muestra el área de Home Assistant asociada (ajustes de la entidad aspiradora → Limpiar habitaciones), o si no el nombre del robot. Escribe un nombre solo para sustituirlo en esta tarjeta.', waiting: 'Esperando las habitaciones del robot…' },
  it: { title: 'Titolo', controls: 'Pulsanti e impostazioni sotto la mappa', rooms: 'Rinomina le stanze solo su questa scheda (facoltativo)',
    rooms_help: 'Di solito lascia vuoto: la scheda mostra l’area di Home Assistant associata (impostazioni dell’entità aspirapolvere → Pulisci stanze), altrimenti il nome dato dal robot. Scrivi un nome solo per sostituirlo su questa scheda.', waiting: 'In attesa delle stanze del robot…' },
};

class YeediMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    if (this._config.entity !== this._entity) {
      this._entity = this._config.entity;
      this._rooms = null;
      this._subscribe();
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._unsub && this._entity) this._subscribe();
    this._render();
  }

  disconnectedCallback() { if (this._unsub) { try { this._unsub(); } catch (e) { /* closed */ } this._unsub = null; } }

  async _subscribe() {
    if (!this._hass || !this._entity || this._subscribing) return;
    if (this._unsub) { try { this._unsub(); } catch (e) { /* closed */ } this._unsub = null; }
    this._subscribing = true;
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (data) => { this._rooms = data.rooms || []; this._render(); },
        { type: 'yeedi/map/subscribe', entity_id: this._entity },
      );
    } catch (e) { this._rooms = []; this._render(); } finally { this._subscribing = false; }
  }

  _t() {
    const lang = (this._hass?.locale?.language || 'en').split('-')[0];
    return { text: EDITOR_TEXT[lang] || EDITOR_TEXT.en, rooms: ROOM_NAMES[lang] || {} };
  }

  _changed(patch) {
    const config = { ...this._config, ...patch };
    for (const k of Object.keys(config)) if (config[k] === '' || config[k] === undefined) delete config[k];
    if (config.room_names && !Object.keys(config.room_names).length) delete config.room_names;
    this._config = config;
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
  }

  _render() {
    if (!this._hass || !this._config) return;
    const { text, rooms } = this._t();
    if (!this._form) {
      this.innerHTML = `
        <style>
          .yeedi-editor { display: flex; flex-direction: column; gap: 16px; }
          .yeedi-editor h4 { margin: 8px 0 0; font-weight: 500; }
          .yeedi-editor .help { font-size: 12px; color: var(--secondary-text-color); margin: -8px 0 0; }
          .yeedi-editor .roomlist { display: flex; flex-direction: column; gap: 8px; }
          .yeedi-editor .roomrow { display: flex; align-items: center; gap: 12px; }
          .yeedi-editor .roomrow span { flex: 0 0 150px; font-size: 14px; color: var(--secondary-text-color); }
          .yeedi-editor .roomrow input { flex: 1; min-width: 0; box-sizing: border-box; height: 40px; padding: 0 12px;
            font: inherit; font-size: 14px; color: var(--primary-text-color); border: 1px solid var(--divider-color);
            border-radius: 8px; background: var(--card-background-color); }
          .yeedi-editor .roomrow input:focus { outline: none; border-color: var(--primary-color); }
        </style>
        <div class="yeedi-editor"><ha-form></ha-form><h4></h4><p class="help"></p><div class="roomlist"></div></div>`;
      this._form = this.querySelector('ha-form');
      this._form.addEventListener('value-changed', (ev) => {
        ev.stopPropagation();
        this._changed(ev.detail.value);
      });
      this._list = this.querySelector('.roomlist');
    }
    this._form.hass = this._hass;
    this._form.data = { entity: this._config.entity || '', title: this._config.title || '', controls: this._config.controls !== false };
    this._form.schema = [
      { name: 'entity', required: true, selector: { entity: { domain: 'vacuum', integration: 'yeedi' } } },
      { name: 'title', selector: { text: {} } },
      { name: 'controls', selector: { boolean: {} } },
    ];
    this._form.computeLabel = (sch) => ({ entity: this._hass.localize('ui.panel.lovelace.editor.card.generic.entity') || 'Entity',
      title: text.title, controls: text.controls }[sch.name] || sch.name);
    this.querySelector('h4').textContent = text.rooms;
    this.querySelector('.help').textContent = text.rooms_help;

    const names = this._config.room_names || {};
    const key = JSON.stringify([this._rooms && this._rooms.map((r) => [r.id, r.name, r.area_name]), names]);
    if (key === this._listKey) return;
    this._listKey = key;
    this._list.innerHTML = '';
    if (!this._rooms) { this._list.textContent = text.waiting; return; }
    for (const room of this._rooms) {
      const row = document.createElement('div'); row.className = 'roomrow';
      const span = document.createElement('span');
      const fallback = room.area_name || rooms[room.robot_name || room.name] || room.robot_name || room.name || '?';
      span.textContent = `${room.id} · ${fallback}`;
      const field = document.createElement('input');
      field.type = 'text';
      field.value = names[room.id] != null ? String(names[room.id]) : '';
      field.placeholder = fallback;
      field.addEventListener('change', () => {
        const next = { ...(this._config.room_names || {}) };
        const v = field.value.trim();
        if (v) next[room.id] = v; else delete next[room.id];
        this._changed({ room_names: next });
      });
      row.append(span, field);
      this._list.append(row);
    }
  }
}

if (!customElements.get('yeedi-map-card-editor')) customElements.define('yeedi-map-card-editor', YeediMapCardEditor);

if (!customElements.get('yeedi-map-card')) customElements.define('yeedi-map-card', YeediMapCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === 'yeedi-map-card')) {
  window.customCards.push({
    type: 'yeedi-map-card',
    name: 'yeedi map',
    description: 'Map of a yeedi robot: rooms, dock, robot and trace, with room cleaning.',
    preview: false,
    documentationURL: 'https://github.com/ciscouf-ops/ha-yeedi',
  });
}
console.info(`%c yeedi-map-card ${CARD_VERSION} `, 'background:#4f8edc;color:#fff;border-radius:3px');
