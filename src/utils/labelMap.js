const FRUIT_LABEL_MAP = {
  apple: '苹果',
  apricot: '杏',
  banana: '香蕉',
  beetroot: '甜菜根',
  blackberry: '黑莓',
  blueberry: '蓝莓',
  broccoli: '西兰花',
  cabbage: '卷心菜',
  capsicum: '甜椒',
  carrot: '胡萝卜',
  cauliflower: '花椰菜',
  chili: '辣椒',
  corn: '玉米',
  cucumber: '黄瓜',
  dates: '椰枣',
  dragonfruit: '火龙果',
  eggplant: '茄子',
  fig: '无花果',
  garlic: '大蒜',
  ginger: '生姜',
  grape: '葡萄',
  guava: '番石榴',
  jalapeno: '墨西哥辣椒',
  kiwi: '猕猴桃',
  lemon: '柠檬',
  lettuce: '生菜',
  mango: '芒果',
  mushroom: '蘑菇',
  onion: '洋葱',
  orange: '橙子',
  papaya: '木瓜',
  pea: '豌豆',
  pear: '梨',
  pineapple: '菠萝',
  pomegranate: '石榴',
  potato: '土豆',
  pumpkin: '南瓜',
  radish: '萝卜',
  raspberry: '树莓',
  soybean: '大豆',
  spinach: '菠菜',
  strawberry: '草莓',
  sweetcorn: '甜玉米',
  sweetpotato: '红薯',
  tomato: '番茄',
  turnip: '芜菁',
  watermelon: '西瓜',
  zucchini: '西葫芦',
  plum: '李子',
  coconut: '椰子'
}

const RIPENESS_LABEL_MAP = {
  ripe: '成熟',
  unripe: '未成熟',
  'half ripe': '半熟',
  'half-ripe': '半熟',
  'Ripe (成熟芒果)': '成熟',
  'Unripe (生芒果)': '未成熟',
  'Ripe (成熟香蕉)': '成熟',
  'Unripe (生香蕉)': '未成熟',
  'Half Ripe (半熟草莓)': '半熟',
  'Ripe (全熟草莓)': '成熟',
  'Unripe (生草莓)': '未成熟'
}

export function translateFruitLabel(label) {
  if (!label || typeof label !== 'string') return label || '-'
  return FRUIT_LABEL_MAP[label] || label
}

export function translateRipenessLabel(label) {
  if (!label || typeof label !== 'string') return label || '-'
  return RIPENESS_LABEL_MAP[label] || RIPENESS_LABEL_MAP[label.toLowerCase()] || label
}
