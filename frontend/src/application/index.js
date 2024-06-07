import "../styles/index.css";

import { Application } from "@hotwired/stimulus";
import { definitionsFromContext } from "@hotwired/stimulus-webpack-helpers";

import Dropdown from 'stimulus-dropdown';
import Reveal from 'stimulus-reveal-controller';
import Dialog from '@stimulus-components/dialog';
import TransitionController from 'stimulus-transition';

// Stimulus
const application = Application.start();
const context = require.context("../controllers", true, /\.js$/);
application.load(definitionsFromContext(context));

application.register('dropdown', Dropdown);
application.register('reveal', Reveal);
application.register('dialog', Dialog);
application.register("transition", TransitionController);
