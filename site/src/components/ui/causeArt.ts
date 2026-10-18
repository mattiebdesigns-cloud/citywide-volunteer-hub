// The cause drawings (PROJECT.md 2; docs/briefs/phase1-home-page.md).
// Drawn for this project and released with it (MIT). Never an organization's
// image, never a photo of people (PROJECT.md 4 rule 2).
// SvgSprite.astro puts each drawing on the page once; CauseArt.astro
// points to it. Add a city's own cause here, plus an --art-<id> colour in
// styles/tokens.css.

// Classes used inside the drawings:
//   a = main colour (navy), b = second colour (coral), c = white,
//   l = ink outline, no fill; cl = white with ink outline;
//   w = white line, no fill; s = soft white shape for depth.
export const art: Record<string, string> = {
  food: `
    <circle class="s" cx="250" cy="40" r="48"/>
    <path class="l" d="M138 52c-8-10 8-16 0-26M160 50c-8-10 8-16 0-26M182 52c-8-10 8-16 0-26"/>
    <path class="a" d="M100 70h120c0 34-27 56-60 56s-60-22-60-56z"/>
    <rect class="b" x="92" y="64" width="136" height="12" rx="6"/>
    <path class="w" d="M120 88c4 12 14 20 26 22"/>
    <rect class="b" x="236" y="40" width="10" height="72" rx="5" transform="rotate(18 241 76)"/>
    <ellipse class="b" cx="231" cy="40" rx="14" ry="20" transform="rotate(18 231 40)"/>`,
  "parks-and-trees": `
    <circle class="b" cx="250" cy="38" r="22"/>
    <ellipse class="a" cx="160" cy="150" rx="210" ry="40" opacity=".35"/>
    <rect class="cl" x="142" y="80" width="16" height="50"/>
    <circle class="a" cx="150" cy="58" r="36"/>
    <circle class="a" cx="122" cy="80" r="24"/>
    <circle class="a" cx="178" cy="80" r="24"/>
    <rect class="c" x="88" y="98" width="8" height="30" rx="2"/>
    <path class="b" d="M92 60l22 44H70z"/>
    <path class="l" d="M92 104v24"/>`,
  animals: `
    <circle class="s" cx="70" cy="40" r="40"/>
    <g transform="translate(150 70)">
      <ellipse class="a" cx="0" cy="18" rx="28" ry="24"/>
      <ellipse class="a" cx="-30" cy="-12" rx="11" ry="14"/>
      <ellipse class="a" cx="-11" cy="-28" rx="11" ry="14"/>
      <ellipse class="a" cx="11" cy="-28" rx="11" ry="14"/>
      <ellipse class="a" cx="30" cy="-12" rx="11" ry="14"/>
    </g>
    <g transform="translate(232 44) rotate(20) scale(.55)">
      <ellipse class="b" cx="0" cy="18" rx="28" ry="24"/>
      <ellipse class="b" cx="-30" cy="-12" rx="11" ry="14"/>
      <ellipse class="b" cx="-11" cy="-28" rx="11" ry="14"/>
      <ellipse class="b" cx="11" cy="-28" rx="11" ry="14"/>
      <ellipse class="b" cx="30" cy="-12" rx="11" ry="14"/>
    </g>`,
  youth: `
    <circle class="s" cx="90" cy="60" r="44"/>
    <path class="b" d="M180 14l40 44-40 56-40-56z"/>
    <path class="l" d="M180 14v100M140 58h80"/>
    <path class="l" d="M180 114c-10 14 6 24-6 36s-24 10-36 22"/>
    <path class="a" d="M170 136l-12-6 2 13zM146 158l-13-3 4 12z"/>`,
  housing: `
    <circle class="s" cx="262" cy="34" r="34"/>
    <rect class="a" x="70" y="40" width="60" height="100"/>
    <rect class="b" x="130" y="30" width="60" height="110"/>
    <rect class="a" x="190" y="46" width="60" height="94"/>
    <path class="l" d="M66 40h68M126 30h68M186 46h68"/>
    <rect class="c" x="82" y="54" width="14" height="18"/><rect class="c" x="106" y="54" width="14" height="18"/>
    <rect class="c" x="142" y="44" width="14" height="18"/><rect class="c" x="164" y="44" width="14" height="18"/>
    <rect class="c" x="202" y="60" width="14" height="18"/><rect class="c" x="226" y="60" width="14" height="18"/>
    <rect class="c" x="90" y="88" width="20" height="30" rx="10"/>
    <rect class="a" x="150" y="80" width="20" height="30" rx="10"/>
    <rect class="c" x="210" y="92" width="20" height="30" rx="10"/>`,
  elders: `
    <circle class="s" cx="160" cy="70" r="56"/>
    <path class="l" d="M104 44c-6-8 6-12 0-20M124 44c-6-8 6-12 0-20M200 44c-6-8 6-12 0-20M220 44c-6-8 6-12 0-20"/>
    <path class="a" d="M92 54h48v44a14 14 0 0 1-14 14h-20a14 14 0 0 1-14-14z"/>
    <path class="l" d="M140 64h6a10 10 0 0 1 0 20h-6"/>
    <path class="b" d="M188 54h48v44a14 14 0 0 1-14 14h-20a14 14 0 0 1-14-14z"/>
    <path class="l" d="M188 64h-6a10 10 0 0 0 0 20h6"/>
    <path class="a" d="M164 40s-12-7-12-15a6 6 0 0 1 12-2 6 6 0 0 1 12 2c0 8-12 15-12 15z"/>`,
  "civic-action": `
    <circle class="s" cx="250" cy="44" r="40"/>
    <rect class="a" x="110" y="24" width="100" height="116" rx="10"/>
    <rect class="b" x="138" y="14" width="44" height="20" rx="6"/>
    <rect class="c" x="124" y="44" width="72" height="88" rx="4"/>
    <path class="l" d="m134 62 6 6 10-12M158 62h28M134 88l6 6 10-12M158 88h28M134 114l6 6 10-12M158 114h20"/>`,
  education: `
    <circle class="s" cx="70" cy="40" r="36"/>
    <path class="a" d="M160 46c-22-12-46-14-74-10v80c28-4 52-2 74 10z"/>
    <path class="b" d="M160 46c22-12 46-14 74-10v80c-28-4-52-2-74 10z"/>
    <path class="l" d="M160 46v80"/>
    <path class="w" d="M100 56c16-2 30 0 44 6M100 74c16-2 30 0 44 6M176 62c14-6 28-8 44-6M176 80c14-6 28-8 44-6"/>
    <g transform="rotate(35 252 70)"><rect class="b" x="246" y="20" width="12" height="70"/><path class="a" d="M246 90h12l-6 14z"/></g>`,
  health: `
    <circle class="s" cx="250" cy="40" r="40"/>
    <path class="a" d="M160 132s-62-36-62-80a32 32 0 0 1 62-12 32 32 0 0 1 62 12c0 44-62 80-62 80z"/>
    <path class="w" d="M108 74h28l10-20 14 40 12-26 8 6h32"/>
    <circle class="b" cx="80" cy="40" r="12"/>`,
  clothing: `
    <circle class="s" cx="80" cy="50" r="40"/>
    <path class="l" d="M160 34a10 10 0 1 1 10-10M160 34v8M160 42 94 70h132z"/>
    <path class="a" d="M128 58l-36 18 12 26 18-8v46h76V94l18 8 12-26-36-18c-4 12-16 20-32 20s-28-8-32-20z"/>
    <path class="b" d="M144 58c4 8 8 12 16 12s12-4 16-12z"/>`,
  repair: `
    <circle class="s" cx="250" cy="44" r="40"/>
    <g transform="translate(220 60)">
      <circle class="b" r="28"/>
      <g class="b"><rect x="-7" y="-40" width="14" height="16"/><rect x="-7" y="24" width="14" height="16"/><rect x="-40" y="-7" width="16" height="14"/><rect x="24" y="-7" width="16" height="14"/></g>
      <circle class="c" r="11"/>
    </g>
    <g transform="rotate(-40 140 76)">
      <rect class="a" x="132" y="40" width="16" height="96" rx="8"/>
      <path class="a" d="M118 26a24 24 0 0 0 44 0l-8-8h-6v18h-16V18h-6z"/>
    </g>
    <g transform="rotate(40 140 76)">
      <rect class="b" x="134" y="70" width="12" height="70" rx="6"/>
      <rect class="cl" x="137" y="22" width="6" height="50"/>
    </g>`,
};

export const fallback = `
    <circle class="s" cx="80" cy="44" r="40"/>
    <rect class="c" x="110" y="26" width="100" height="100" rx="10"/>
    <rect class="a" x="110" y="26" width="100" height="26" rx="10"/>
    <rect class="a" x="110" y="40" width="100" height="12"/>
    <path class="l" d="M135 18v18M185 18v18"/>
    <path class="b" d="m160 64 7 14 15 2-11 10 3 15-14-7-14 7 3-15-11-10 15-2z"/>`;

/** The symbol id for a cause, or the fallback for null and unknown ids. */
export function artId(cause: string | null | undefined): string {
  return cause && art[cause] ? cause : "default";
}
