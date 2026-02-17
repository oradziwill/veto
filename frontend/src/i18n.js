import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en.json'
import pl from './locales/pl.json'

const savedLanguage = localStorage.getItem('veto-language') || 'pl'

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      pl: { translation: pl },
    },
    lng: savedLanguage,
    fallbackLng: 'pl',
    interpolation: {
      escapeValue: false, // React already escapes
    },
  })

export default i18n
