# PSYC2016lectures

These lectures are rendered to e.g. https://alexholcombe.github.io/PSYC2016lectures

This happens thanks to configuring the repository to render to docs/, adding a .nojekyll file, and telling Github to publish from the docs directory, as all explained here:

https://quarto.org/docs/publishing/github-pages.html#render-to-docs

So whenever I push to github here, the new version will be published.

## Figured out how to add more space below slide titles

In styles.scss:

/*-- scss:rules --*/

.reveal .slides h2 {
    margin-bottom: 40px; /* Adjust the value as needed */
}


See
css-files-https-community-rstudio-com-t-how-to-increase-the-spacing-between-item-lists-in-a-revealjs-presentation-using-quarto-170579-2-u-tchevri/173432

and https://github.com/hakimel/reveal.js/blob/master/css/theme/template/theme.scss