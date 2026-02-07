const logic = (score, team) => {
    let result = 'D';
    const [scoreA, scoreB] = score.split(':').map(Number);

    console.log(`Score: ${scoreA}:${scoreB}, Team: ${team}`);

    if (team === 'White') {
        if (scoreA > scoreB) result = 'W';
        else if (scoreA < scoreB) result = 'L';
    } else if (team === 'Red') {
        if (scoreB > scoreA) result = 'W';
        else if (scoreB < scoreA) result = 'L';
    }
    return result;
};

console.log("White 6:3 ->", logic("6:3", "White")); // Should be W
console.log("Red 6:3 ->", logic("6:3", "Red"));     // Should be L
console.log("White 3:6 ->", logic("3:6", "White")); // Should be L
console.log("Red 3:6 ->", logic("3:6", "Red"));     // Should be W
console.log("White 2:2 ->", logic("2:2", "White")); // Should be D
