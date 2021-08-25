## Building locally
To work locally with this project, you'll have to follow the steps below:

1. Fork, clone or download this project
2. [Install Hugo](https://gohugo.io/getting-started/installing/) 
    ```
    $ dnf install hugo
    ```
3. Make changes to website `/content/`
4. Preview your project: `$ hugo server`
this will spin up a localhost web server to test your wesite. 
5. Generate the static website in `/public/` dir: 
    `$ hugo` (optional)

### Preview your site

If you clone or download this project to your local computer and run `hugo server`,
your site can be accessed under `localhost:1313`.

## Site Layout
1. Any text content to be updated should be done inside `/content/` dir
    * `/content/docs/` add/update/delete docs content.
    * `/content/post/` add/update/delete post or blog content
    * `/content/_index.md` is the landing page/overview content.
2. All the images, videos, gif, text file used in website is stored in `/static/` dir. 
3. Any HTML design changes to be overridden then use the `/layouts/` dir
4. All the website configuration like baseURL, menu tabs names & route, color schemes, title and etc are mentioned in `/config.toml`
5. Our theme used is inside `/themes/cayman-hugo-theme/` dir. If you want to refer sample example to how to use this theme refer `/themes/cayman-hugo-theme/exampleSite/`

## Credits
The theme used is [cayman-hugo-theme](https://themes.gohugo.io/themes/cayman-hugo-theme)