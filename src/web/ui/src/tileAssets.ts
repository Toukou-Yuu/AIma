/** 与 ``src/ui/tiles.tile_to_filename`` 规则一致，供静态路径拼接。 */

export function tileCodeToFilename(code: string): string {
  const s = code.trim().toLowerCase();
  const red = /^5([mps])r$/.exec(s);
  if (red) return `5${red[1]}_red.png`;
  const num = /^([1-9])([mps])$/.exec(s);
  if (num) return `${num[1]}${num[2]}.png`;
  const hon = /^([1-7])z$/.exec(s);
  if (hon) return `${hon[1]}z.png`;
  return "1m.png";
}

export function tileImageSrc(code: string): string {
  return `/assets/tiles/${tileCodeToFilename(code)}`;
}

/** 牌背（若资源不存在，请配合 CSS 占位或 onError） */
export function backImageSrc(): string {
  return "/assets/tiles/back_orange.png";
}
