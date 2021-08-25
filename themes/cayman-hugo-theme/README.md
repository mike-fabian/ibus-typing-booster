# Cayman

[![Netlify Status](https://api.netlify.com/api/v1/badges/a050ba7f-deca-43ea-9e70-677784edf90c/deploy-status)](https://app.netlify.com/sites/cayman-hugo-theme/deploys)

Cayman is a clean, responsive theme for Hugo, ported from the original Jekyll Cayman Theme.

## Table of contents

- [Demo](#demo)
- [Minimum Hugo version](#minimum-hugo-version)
- [Installation](#installation)
- [Updating](#updating)
- [Run example site](#run-example-site)
- [Configuration](#configuration)
- [Favicons](#favicons)
- [Getting help](#getting-help)
- [Credits](#credits)
- [License](#license)

## Demo

https://cayman-hugo-theme.netlify.com/

## Minimum Hugo version

Hugo version `0.81.0` or higher is required. View the [Hugo releases](https://github.com/gohugoio/hugo/releases) and download the binary for your OS.

**Note**: The extended version of Hugo is only required if you wish to edit style-related params in your config file. This is because this theme uses Hugo Pipes and SCSS. 

## Installation

From the root of your site:

```
git submodule add https://github.com/zwbetz-gh/cayman-hugo-theme.git themes/cayman-hugo-theme
```

## Updating

From the root of your site:

```
git submodule update --remote --merge
```

## Run example site

From the root of `themes/cayman-hugo-theme/exampleSite`:

```
hugo server --themesDir ../..
```

## Configuration

Copy the `config.toml` **or** `config.yaml` from the [`exampleSite`](https://github.com/zwbetz-gh/cayman-hugo-theme/tree/master/exampleSite), then edit as desired. 

When editing the header background colors, [this site](http://uigradients.com) has some nice color combinations. 

## Favicons

Upload your image to [RealFaviconGenerator](https://realfavicongenerator.net/) then copy-paste the generated favicon files under `static`. 

## Getting help

If you run into an issue that isn't answered by this documentation or the [`exampleSite`](https://github.com/zwbetz-gh/cayman-hugo-theme/tree/master/exampleSite), then visit the [Hugo forum](https://discourse.gohugo.io/). The folks there are helpful and friendly. **Before** asking your question, be sure to read the [requesting help guidelines](https://discourse.gohugo.io/t/requesting-help/9132).

## Credits

Thank you to [Jason Long](https://github.com/jasonlong) for creating the original Jekyll [Cayman Theme](https://github.com/jasonlong/cayman-theme). 

## License

[Creative Commons Attribution 4.0 International](http://creativecommons.org/licenses/by/4.0/). 
