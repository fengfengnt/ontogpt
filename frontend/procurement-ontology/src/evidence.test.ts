import { evidence } from './evidence';

test('browser evidence uses Python Unicode offsets on unchanged original text', () => {
  const source = { id: 's1', text: '原厂😀\r\n原厂上门', simulated: true, sha256: '' };
  expect(evidence(source, '原厂上门')).toEqual({ revision_id: 's1', start: 5, end: 9, quote: '原厂上门' });
  expect(() => evidence({ ...source, text: 'aaaa' }, 'aaa')).toThrow('唯一定位');
  expect(() => evidence(source, '不存在')).toThrow('唯一定位');
});
