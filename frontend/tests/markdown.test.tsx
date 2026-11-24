import {describe,it,expect,vi,afterEach} from 'vitest';
import {render,cleanup,fireEvent} from '@testing-library/react';
import {Markdown} from '../src/Markdown';
afterEach(cleanup);
describe('research Markdown',()=>{
 it('renders matrices, piecewise functions, derivatives, expectation, sum, integral',()=>{
  const equations=[String.raw`J=\begin{bmatrix}\frac{\partial f}{\partial x}&0\\0&1\end{bmatrix}`,String.raw`f(x)=\begin{cases}x^2&x\ge0\\-x&x<0\end{cases}`,String.raw`\mathbb{E}[X]=\sum_{i=1}^n x_i p_i=\int_{-\infty}^\infty xp(x)\,dx`];
  const {container}=render(<Markdown text={equations.map(e=>'$$\n'+e+'\n$$').join('\n\n')}/>);
  expect(container.querySelectorAll('.katex-display').length).toBe(3);
  expect(container.querySelector('.katex-error')).toBeNull();
  expect(container.querySelectorAll('math').length).toBe(3);
 });
 it('renders tables, tasks and highlighted Python',()=>{
  const {container}=render(<Markdown text={'| x | y |\n| - | - |\n| 1 | 2 |\n\n- [x] done\n\n```python\ndef f(x):\n    return x ** 2\n```'}/>);
  expect(container.querySelector('table')).not.toBeNull();
  expect(container.querySelector('input[type=checkbox]')).not.toBeNull();
  expect(container.querySelector('.hljs-keyword')).not.toBeNull();
 });
 it('blocks executable HTML, unsafe URLs, remote images and untrusted KaTeX HTML',()=>{
  const {container}=render(<Markdown text={'<script>window.hacked=true</script>\n\n<img src=x onerror=alert(1)>\n\n[bad](javascript:alert%281%29)\n\n![tracking](https://evil.example/a.png)\n\n$\\href{javascript:alert(1)}{x}$'}/>);
  expect(container.querySelector('script')).toBeNull();expect(container.querySelector('img')).toBeNull();
  expect(container.innerHTML).not.toMatch(/href="javascript:/);
 });
 it('opens stable internal knowledge links',()=>{
  const open=vi.fn();const {getByText}=render(<Markdown text={'[BPTT](#node/abc-123)'} onOpen={open}/>);
  fireEvent.click(getByText('BPTT'));expect(open).toHaveBeenCalledWith('abc-123');
 });
});
