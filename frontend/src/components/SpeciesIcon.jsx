import { Dog, Cat, Bird, Rabbit, Squirrel, PawPrint } from 'lucide-react'

const getSpeciesKey = (species) => {
  const s = (species || '').toLowerCase()
  if (s.includes('dog') || s.includes('pies') || s.includes('canis')) return 'dog'
  if (s.includes('cat') || s.includes('kot') || s.includes('felis')) return 'cat'
  if (s.includes('rabbit') || s.includes('krol') || s.includes('królik')) return 'rabbit'
  if (s.includes('bird') || s.includes('ptak') || s.includes('aves')) return 'bird'
  if (s.includes('hamster') || s.includes('chomik')) return 'hamster'
  return 'default'
}

const ICON_MAP = {
  dog: Dog,
  cat: Cat,
  rabbit: Rabbit,
  bird: Bird,
  hamster: Squirrel,
  default: PawPrint,
}

const SpeciesIcon = ({ species, size = 40, color = 'currentColor', className = '' }) => {
  const key = getSpeciesKey(species)
  const Icon = ICON_MAP[key]
  return <Icon size={size} color={color} className={className} aria-label={species || 'animal'} strokeWidth={1.5} />
}

export { getSpeciesKey }
export default SpeciesIcon
