// Four robots as the card sees them: the yeedi vac max (rooms, water levels), the vac
// station (auto-empty, cleaning some rooms), the M16 Infinity (water flow number,
// mop-washing station) and the yeedi 2 hybrid (no room outlines, rooms as buttons).
const sq = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
const ROOMS = [
  { id: 1, name: 'Living Room', outline: sq(0, 0, 5000, 4000) },
  { id: 2, name: 'Kitchen', outline: sq(5000, 0, 3000, 4000) },
  { id: 3, name: 'Bedroom', outline: sq(0, 4000, 4000, 3000) },
];
const base = (state, extra) => ({
  'vacuum.robot': { state, attributes: { friendly_name: 'Robot', fan_speed_list: ['quiet', 'normal', 'max'] } },
  'sensor.robot_battery': { state: '80', attributes: { device_class: 'battery' } },
  'select.robot_suction': { key: 'suction', state: 'normal', attributes: { options: ['quiet', 'normal', 'max', 'max_plus'] } },
  'sensor.robot_area': { key: 'stats_area', state: '23', attributes: { unit_of_measurement: 'm²' } },
  'sensor.robot_time': { key: 'stats_time', state: '31', attributes: { unit_of_measurement: 'min' } },
  ...extra,
});
const map = (extra) => ({ map_id: '1', rooms: ROOMS, robot: { x: 1000, y: 1000, a: 0 }, dock: { x: 7500, y: 500, a: 90 },
  no_mop: [], walls: [], trace: [], state: 'docked', history: [], ...extra });

module.exports = {
  vac_max: {
    entities: base('docked', {
      'select.robot_water': { key: 'water_amount', state: 'low', attributes: { options: ['low', 'medium', 'high', 'ultrahigh'] } },
    }),
    data: map(),
  },
  vac_station: {
    entities: base('cleaning', {
      'button.robot_empty': { key: 'station_empty_dustbin', state: 'unknown' },
    }),
    data: map({ state: 'cleaning', trace: [[1000, 1000], [3000, 1000], [3000, 2000]],
      progress: { room_id: 2, room: 'Kitchen', remaining_minutes: 9, end: Date.now() / 1000 + 540, progress: 40, planned: [2, 1, 3] } }),
  },
  m16: {
    entities: base('docked', {
      'number.robot_water': { key: 'water_amount', state: '30', attributes: { min: 0, max: 50, step: 1 } },
      'binary_sensor.robot_clean': { key: 'clean_water_empty', state: 'on' },
      'binary_sensor.robot_dirty': { key: 'dirty_water_full', state: 'off' },
      'button.robot_empty': { key: 'station_empty_dustbin', state: 'unknown' },
      'button.robot_wash': { key: 'station_wash_mop', state: 'unknown' },
      'button.robot_dry': { key: 'station_dry_mop', state: 'unknown' },
    }),
    data: map({ history: [{ end: Date.now() / 1000 - 3600, minutes: 42, area: 35.5, rooms: ['Kitchen'], result: 'finished' }] }),
  },
  hybrid: {
    entities: base('docked', {}),
    data: map({ rooms: ROOMS.map((r) => ({ ...r, outline: [] })) }),
  },
};
