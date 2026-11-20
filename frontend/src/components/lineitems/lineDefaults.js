export const GST_RATES = ['0', '5', '12', '18', '28'];

export const emptyMaterialLine = () => ({
  item_type: 'MATERIAL',
  material: '',
  description: '',
  hsn_code: '',
  quantity: '',
  unit: '',
  rate: '',
  discount_percent: '0',
  gst_rate: '18',
});

export const emptyServiceLine = () => ({
  item_type: 'SERVICE',
  material: null,
  description: '',
  hsn_code: '',
  quantity: '1',
  unit: 'ls',
  rate: '',
  discount_percent: '0',
  gst_rate: '18',
});
