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

const CARD_VERSION = '0.2.0';

const TEXT = {
  en: {
    clean: 'Clean', clean_rooms: (n) => `Clean ${n} room${n > 1 ? 's' : ''}`, pause: 'Pause',
    resume: 'Resume', dock: 'Dock', clear: 'Clear', no_map: 'Waiting for the map…',
    no_outline: 'The robot did not send the outline of the rooms: choose them below.',
    not_yeedi: 'This entity is not a yeedi vacuum.', fan: 'Suction', water: 'Water',
    states: { cleaning: 'Cleaning', returning: 'Returning to the dock', docked: 'Docked',
      idle: 'Idle', paused: 'Paused', error: 'Error' },
    since: 'started at',
  },
  fr: {
    clean: 'Nettoyer', clean_rooms: (n) => `Nettoyer ${n} pièce${n > 1 ? 's' : ''}`, pause: 'Pause',
    resume: 'Reprendre', dock: 'Base', clear: 'Effacer', no_map: 'En attente de la carte…',
    no_outline: "Le robot n'a pas envoyé le contour des pièces : choisis-les ci-dessous.",
    not_yeedi: "Cette entité n'est pas un aspirateur yeedi.", fan: 'Aspiration', water: 'Eau',
    states: { cleaning: 'Nettoyage', returning: 'Retour à la base', docked: 'Sur la base',
      idle: 'À l’arrêt', paused: 'En pause', error: 'Erreur' },
    since: 'commencé à',
  },
};

// Generic room names sent by the robot (deebot-client), translated.
const ROOM_NAMES = {
  fr: { 'Default': 'Pièce', 'Living Room': 'Séjour', 'Dining Room': 'Salle à manger',
    'Bedroom': 'Chambre', 'Study': 'Bureau', 'Kitchen': 'Cuisine', 'Bathroom': 'Salle de bain',
    'Laundry': 'Buanderie', 'Lounge': 'Salon', 'Storeroom': 'Débarras',
    'Kids room': 'Chambre d’enfant', 'Sunroom': 'Véranda', 'Corridor': 'Couloir',
    'Balcony': 'Balcon', 'Gym': 'Salle de sport' },
};

const PALETTE = ['#4f8edc', '#e0a04a', '#5bb07a', '#c46fb8', '#d96a5c', '#4fb3bf', '#9a8bd6', '#b5a046'];

class YeediMapCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        { name: 'entity', required: true, selector: { entity: { domain: 'vacuum', integration: 'yeedi' } } },
        { name: 'title', selector: { text: {} } },
        { name: 'controls', selector: { boolean: {} } },
      ],
    };
  }

  static getStubConfig(hass) {
    const entity = Object.values(hass.entities || {}).find(
      (e) => e.platform === 'yeedi' && e.entity_id.startsWith('vacuum.'),
    );
    return { entity: entity ? entity.entity_id : '' };
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error('entity is required');
    const changed = !this._config || this._config.entity !== config.entity;
    this._config = { controls: true, ...config };
    this._selected = [];
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
        (data) => { this._data = data; this._error = null; this._render(); },
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
    return { battery: battery?.entity_id, water: water?.entity_id };
  }

  _otherStates() {
    const r = this._related();
    return [r.battery, r.water].map((e) => (e ? this._hass.states[e]?.state : '')).join('|');
  }

  _roomName(room) {
    const custom = this._config.room_names || {};
    if (custom[room.id] != null) return String(custom[room.id]);
    const { rooms } = this._t();
    return rooms[room.name] || room.name || `#${room.id}`;
  }

  // ------------------------------------------------------------- actions

  _call(service, data = {}) {
    this._hass.callService('vacuum', service, { entity_id: this._config.entity, ...data });
  }

  _cleanSelected() {
    if (!this._selected.length) { this._call('start'); return; }
    this._call('send_command', {
      command: 'spot_area',
      params: { rooms: this._selected.join(','), cleanings: 1 },
    });
    this._selected = [];
    this._render();
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
    }
    const { text } = this._t();
    const st = this._hass?.states?.[this._config.entity];
    const title = this._config.title ?? st?.attributes?.friendly_name ?? 'yeedi';
    const moving = ['cleaning', 'returning'].includes(st?.state);
    const r = this._related();
    const battery = r.battery ? this._hass.states[r.battery]?.state : null;
    const status = [text.states[st?.state] || st?.state || '', battery && !isNaN(battery) ? `${Math.round(battery)} %` : '']
      .filter(Boolean).join(' · ');

    let body;
    if (this._error) body = `<div class="msg">${text[this._error]}</div>`;
    else if (!this._data) body = `<div class="msg">${text.no_map}</div>`;
    else body = this._map(moving);

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="head">
          <div class="title">${esc(title)}</div>
          <div class="status">${esc(status)}</div>
        </div>
        ${body}
        ${this._config.controls !== false && st ? this._controls(st, r, moving) : ''}
      </ha-card>`;
  }

  _map(moving) {
    const { text } = this._t();
    const d = this._data;
    const rooms = d.rooms.filter((x) => x.outline && x.outline.length > 2);
    const pts = [];
    rooms.forEach((x) => pts.push(...x.outline));
    if (d.dock) pts.push([d.dock.x, d.dock.y]);
    if (d.robot) pts.push([d.robot.x, d.robot.y]);
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
      const font = Math.round(u * 2.6);
      const choose = !moving;
      let s = `<svg viewBox="0 0 ${W.toFixed(0)} ${H.toFixed(0)}" preserveAspectRatio="xMidYMid meet">`;
      rooms.forEach((room, i) => {
        const sel = this._selected.indexOf(room.id);
        s += `<polygon class="room${choose ? ' pick' : ''}${sel >= 0 ? ' sel' : ''}" data-room="${room.id}"
          points="${P(room.outline)}" style="--c:${PALETTE[i % PALETTE.length]}"/>`;
      });
      if (moving && d.trace && d.trace.length > 1) {
        if (rooms.length) s += `<clipPath id="inside">${rooms.map((x) => `<polygon points="${P(x.outline)}"/>`).join('')}</clipPath>`;
        const clip = rooms.length ? ' clip-path="url(#inside)"' : '';
        s += `<polyline class="band" points="${P(d.trace)}"${clip}/>`;
        s += `<polyline class="line" points="${P(d.trace)}"${clip}/>`;
      }
      rooms.forEach((room) => {
        const rx = room.outline.map((p) => p[0]), ry = room.outline.map((p) => p[1]);
        const cx = X((Math.min(...rx) + Math.max(...rx)) / 2), cy = Y((Math.min(...ry) + Math.max(...ry)) / 2);
        const sel = this._selected.indexOf(room.id);
        const label = (sel >= 0 ? `${sel + 1}. ` : '') + this._roomName(room);
        s += `<text class="name" x="${cx}" y="${cy}" font-size="${font}">${esc(label)}</text>`;
      });
      if (d.dock) {
        s += `<g transform="translate(${X(d.dock.x)},${Y(d.dock.y)})"><g transform="scale(${(u / 75).toFixed(3)})"><rect x="-190" y="-190" width="380" height="380" rx="90" class="dock"/>
          <path transform="translate(-144,-144) scale(12)" fill="#fff" d="M12 3L2 12h3v8h14v-8h3L12 3z"/></g></g>`;
      }
      if (d.robot && !(st_docked(this) && d.dock)) {
        const a = ((d.robot.a || 0) * Math.PI) / 180;
        const hx = Math.cos(a) * 120, hy = -Math.sin(a) * 120;
        s += `<g transform="translate(${X(d.robot.x)},${Y(d.robot.y)}) scale(${(u / 75).toFixed(3)})">
          ${moving ? '<circle r="320" class="halo"/>' : ''}
          <circle r="170" class="robot"/><line x1="0" y1="0" x2="${hx.toFixed(0)}" y2="${hy.toFixed(0)}" class="heading"/></g>`;
      }
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
    let main;
    if (moving) main = `<button class="btn" data-act="pause"><ha-icon icon="mdi:pause"></ha-icon>${text.pause}</button>`;
    else if (paused) main = `<button class="btn" data-act="resume"><ha-icon icon="mdi:play"></ha-icon>${text.resume}</button>`;
    else main = `<button class="btn" data-act="clean"><ha-icon icon="mdi:play"></ha-icon>${n ? text.clean_rooms(n) : text.clean}</button>`;
    const clear = n && !moving ? `<button class="btn flat" data-act="clear">${text.clear}</button>` : '';
    const dock = st.state !== 'docked' ? `<button class="btn flat" data-act="dock"><ha-icon icon="mdi:home-import-outline"></ha-icon>${text.dock}</button>` : '';

    const fanList = st.attributes.fan_speed_list || [];
    const fan = fanList.length ? `<div class="row"><span class="lbl">${text.fan}</span><div class="chips">${fanList.map((f) => {
      const label = this._hass.formatEntityAttributeValue ? this._hass.formatEntityAttributeValue(st, 'fan_speed', f) : f;
      const icon = f === 'mop_only' ? '<ha-icon icon="mdi:fan-off"></ha-icon>' : '';
      return `<button class="chip${st.attributes.fan_speed === f ? ' on' : ''}" data-fan="${f}">${icon}${esc(label)}</button>`;
    }).join('')}</div></div>` : '';

    const wst = related.water ? this._hass.states[related.water] : null;
    const water = wst && wst.attributes.options ? `<div class="row"><span class="lbl">${text.water}</span><div class="chips">${wst.attributes.options.map((o) => {
      const label = this._hass.formatEntityState ? this._hass.formatEntityState(wst, o) : o;
      return `<button class="chip${wst.state === o ? ' on' : ''}" data-water="${o}">${esc(label)}</button>`;
    }).join('')}</div></div>` : '';

    return `<div class="actions">${main}${clear}${dock}</div>${fan}${water}`;
  }

  _onClick(ev) {
    const path = ev.composedPath();
    const el = path.find((n) => n.dataset && (n.dataset.room || n.dataset.act || n.dataset.fan || n.dataset.water));
    if (!el || el.disabled) return;
    const st = this._hass.states[this._config.entity];
    if (el.dataset.room) {
      if (['cleaning', 'returning'].includes(st?.state)) return;
      this._toggleRoom(Number(el.dataset.room));
    } else if (el.dataset.act === 'clean') this._cleanSelected();
    else if (el.dataset.act === 'pause') this._call('pause');
    else if (el.dataset.act === 'resume') this._call('start');
    else if (el.dataset.act === 'dock') this._call('return_to_base');
    else if (el.dataset.act === 'clear') { this._selected = []; this._render(); }
    else if (el.dataset.fan) this._call('set_fan_speed', { fan_speed: el.dataset.fan });
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
  .status { font-size: 13px; color: var(--secondary-text-color); white-space: nowrap; }
  .map { padding: 4px 12px; }
  svg { width: 100%; height: auto; max-height: 420px; display: block; }
  .room { fill: var(--c); fill-opacity: .28; stroke: var(--card-background-color, #fff); stroke-width: 40; stroke-linejoin: round; transition: fill-opacity .2s; }
  .room.pick { cursor: pointer; }
  .room.pick:hover { fill-opacity: .4; }
  .room.sel { fill-opacity: .62; }
  .name { text-anchor: middle; dominant-baseline: middle; fill: var(--primary-text-color); font-weight: 500;
          paint-order: stroke; stroke: var(--card-background-color, #fff); stroke-width: 40; stroke-linejoin: round; pointer-events: none; }
  .band { fill: none; stroke: var(--primary-color); stroke-opacity: .16; stroke-width: 260; stroke-linecap: round; stroke-linejoin: round; }
  .line { fill: none; stroke: var(--primary-color); stroke-opacity: .7; stroke-width: 22; stroke-linecap: round; stroke-linejoin: round; }
  .dock { fill: #43a047; stroke: #fff; stroke-width: 35; }
  .robot { fill: var(--primary-color); stroke: #fff; stroke-width: 40; }
  .heading { stroke: #fff; stroke-width: 40; stroke-linecap: round; }
  .halo { fill: var(--primary-color); opacity: .18; animation: pulse 2s ease-in-out infinite; }
  @keyframes pulse { 50% { opacity: .05; } }
  .msg { padding: 24px 16px; text-align: center; color: var(--secondary-text-color); font-size: 13px; }
  .msg.small { padding: 8px 16px 4px; }
  .actions { display: flex; gap: 8px; padding: 10px 16px 6px; flex-wrap: wrap; }
  .btn { display: inline-flex; align-items: center; gap: 6px; border: none; border-radius: 18px; padding: 8px 16px;
         font: 500 14px var(--paper-font-body1_-_font-family, inherit); cursor: pointer;
         background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .btn.flat { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); color: var(--primary-text-color); }
  .btn ha-icon { --mdc-icon-size: 18px; }
  .row { display: flex; align-items: center; gap: 10px; padding: 4px 16px; }
  .row:last-child { padding-bottom: 14px; }
  .lbl { font-size: 12px; color: var(--secondary-text-color); min-width: 72px; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; padding: 2px 0; }
  .msg + .chips { padding: 4px 16px 8px; }
  .chip { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--divider-color); border-radius: 14px;
          padding: 4px 11px; font-size: 12px; cursor: pointer; background: none; color: var(--primary-text-color); }
  .chip.on { background: color-mix(in srgb, var(--primary-color) 18%, transparent); border-color: var(--primary-color); }
  .chip:disabled { opacity: .5; cursor: default; }
  .chip ha-icon { --mdc-icon-size: 14px; }
`;

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
