export const SPECIES_KEYS = {
  "Dog": "speciesDog",
  "Cat": "speciesCat",
  "Rabbit": "speciesRabbit",
  "Mouse": "speciesMouse",
  "Hamster": "speciesHamster",
  "Guinea pig": "speciesGuineaPig",
  "Bird": "speciesBird",
  "Ferret": "speciesFerret",
  "Other": "speciesOther",
};

export const translateSpecies = (species, t) => {
  const key = SPECIES_KEYS[species];
  return key ? t(`addPatient.${key}`) : (species || "");
};
