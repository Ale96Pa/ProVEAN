import './app.css'
import App from './App.svelte'
import '@lib/polyfills'

const app = new App({
  target: document.getElementById('app')!,
})

export default app
