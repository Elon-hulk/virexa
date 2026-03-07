export default defineAppConfig({
  github: {
    url: "https://github.com/yousumohamed",
    branch: "main",
    rootDir: "",
  },
  docus: {
    title: 'Virexa',
    description: 'The best place to start your professional Discord server logging and moderation.',
    image: 'https://cdn.discordapp.com/embed/avatars/0.png',
    socials: {
      github: ''
    },
    aside: {
      level: 0,
      collapsed: false,
      exclude: []
    },
    header: {
      logo: false,
      title: 'Virexa Docs',
      showLinkIcon: true,
      exclude: []
    },
    footer: {
      credits: {
        text: 'Powered by Virexa',
        icon: 'IconDocus',
        href: '/'
      }
    }
  },
  ui: {
    primary: 'sky',
    gray: 'slate'
  }
});