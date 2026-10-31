import {test, expect} from 'vitest';
import {totalCents} from '../src/money';
test('sums decimal prices as integer cents',()=>expect(totalCents([1.25,2.5])).toBe(375));
test('avoids floating point accumulation',()=>expect(totalCents([0.1,0.2])).toBe(30));
test('empty invoice has zero total',()=>expect(totalCents([])).toBe(0));
