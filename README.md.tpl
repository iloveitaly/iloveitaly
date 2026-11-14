<img align="right" src="https://github-readme-stats.vercel.app/api?username=iloveitaly&show_icons=true&text_color=718096&hide_title=true"/>

- 🔭 I’m currently [building a new startup](https://mikebian.co/bye-stripe-on-to-the-next-adventure/) after selling my [last company](https://suitesync.io) to Stripe
- 📫 I love meeting new people, drop me an email or DM to chat!
- ✍️ I write every so often [on my blog](http://mikebian.co/) and [tweet](https://twitter.com/mike_bianco)
- 🌱 I’m currently enjoying digging into tmux and terminal productivity more (check out my [dotfiles](https://github.com/iloveitaly/dotfiles))
- 💬 I really enjoy personal productivity, check out [hyper-focus](https://github.com/iloveitaly/hyper-focus)

#### 📜 My recent blog posts

{{range rss "https://mikebian.co/feed/" 6}}
- [{{.Title}}]({{.URL}}) ({{humanize .PublishedAt}})
{{- end}}

#### 🌱 My latest projects

{{range recentRepos 6}}
- [{{.Name}}]({{.URL}}) - {{.Description}}
{{- end}}
